from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "components/clientjs-auto/worker/auto_multi_dev_worker.py"
HOST = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_host.py"
GAME_SESSION = ROOT / "components/clientjs-auto/kvtm_automation/workflows/game_session/workflow.py"
PIRATE_CHEST = ROOT / "components/clientjs-auto/kvtm_automation/workflows/pirate_chest/workflow.py"
POPUP = ROOT / "components/clientjs-auto/kvtm_automation/actions/popup.py"
AUTOMATION = ROOT / "components/clientjs-auto/kvtm_automation/automation.py"
MANAGER = ROOT / "components/clientjs-auto/kvtm_automation/recovery/manager.py"
MATERIAL_RECOVERY = ROOT / "components/clientjs-auto/kvtm_automation/recovery/material_shortage.py"
MARKER = ".fresh-client-start.json"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing AUTO lifecycle file: {path}")
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def forbid(text: str, token: str, message: str) -> None:
    if token in text:
        raise AssertionError(message)


def main() -> int:
    worker = read(WORKER)
    host = read(HOST)
    game_session = read(GAME_SESSION)
    pirate_chest = read(PIRATE_CHEST)
    popup = read(POPUP)
    automation = read(AUTOMATION)
    manager = read(MANAGER)
    material_recovery = read(MATERIAL_RECOVERY)

    # One resident-tool session grants exactly one fresh startup gate to each
    # live profile + ClientJS PID generation. This includes ClientJS processes
    # already running/adopted when AUTO is pressed after a tool restart. Stop ->
    # Start on the same PID must not manufacture a second fresh marker.
    require(host, f'_AUTO_MAIN_FRESH_MARKER = "{MARKER}"', "Host fresh marker name changed")
    require(host, "def _install_auto_main_lifecycle_tracking(dev_entry)", "Host lifecycle tracking missing")
    require(host, "original_start = app_cls._start_clean_auto_session", "AUTO Main start is not tracked")
    require(host, "original_launch = app_cls._launch", "ClientJS launch hook missing")
    require(host, "def _mark_fresh_client(self, profile_id: str, process, *, source: str)", "Per-ClientJS fresh marker helper missing")
    require(host, 'key = (profile_id, pid)', "Fresh gate is not keyed by profile + ClientJS PID")
    require(host, 'seen = getattr(self, "_auto_main_fresh_marked_clients", None)', "Tool-session ClientJS generation set missing")
    require(host, "if key in seen:", "Same ClientJS PID can receive duplicate fresh gates")
    require(host, "seen.add(key)", "Fresh ClientJS generation is not remembered")
    require(host, "selected = list(map(str, self.selected_ids()))", "Existing/adopted ClientJS profiles are not inspected on AUTO start")
    require(host, 'source="existing-client-first-auto-start"', "Existing ClientJS first-start fresh marker missing")
    require(host, 'self._auto_main_launch_tracking_depth = previous_depth + 1', "AUTO Main launch scope missing")
    require(host, 'if int(getattr(self, "_auto_main_launch_tracking_depth", 0) or 0) <= 0:', "Non-AUTO launches are not excluded")
    require(host, 'source="auto-launched-client"', "AUTO-launched ClientJS fresh marker missing")
    require(host, 'marker_root = dev_entry.core.APP_DIR / "auto-multi-dev" / profile_id', "Fresh marker is not profile-scoped")
    require(host, '"pid": pid', "Fresh marker does not bind ClientJS PID")
    require(host, '"profile_id": profile_id', "Fresh marker does not bind profile")
    require(host, '"created_at": time.time()', "Fresh marker has no creation timestamp")
    require(host, "marker.write_text(", "Fresh marker is never written")
    require(host, "_install_auto_main_lifecycle_tracking(kvtm_multi_dev_entry)", "Lifecycle hook is not installed")

    # Worker lifecycle resolution is fail-safe: auto is the default; no marker,
    # stale marker, invalid marker, wrong profile, or wrong ClientJS PID all mean
    # re-entry. A valid marker is one-shot and is consumed before bootstrap.
    require(worker, f'_AUTO_MAIN_FRESH_MARKER = "{MARKER}"', "Worker fresh marker name changed")
    require(worker, 'choices=("auto", "fresh", "reentry"), default="auto"', "Worker startup mode must default to auto")
    require(worker, "def _resolve_startup_mode(args)", "Worker lifecycle resolver missing")
    require(worker, 'return "reentry", "no-fresh-launch-marker"', "No-marker path must be re-entry")
    require(worker, "marker.unlink(missing_ok=True)", "Fresh marker is not one-shot")
    require(worker, 'if marker_profile != str(args.profile_id):', "Fresh marker profile binding missing")
    require(worker, 'if marker_pid != int(args.pid):', "Fresh marker ClientJS PID binding missing")
    require(worker, '_FRESH_MARKER_MAX_AGE_SECONDS', "Fresh marker staleness bound missing")
    require(worker, 'return "fresh", f"fresh-launch-marker-match:age={age:.1f}s"', "Valid marker does not resolve fresh")
    require(worker, "startup_mode, startup_mode_reason = _resolve_startup_mode(args)", "Resolved lifecycle is not consumed")
    require(worker, 'if startup_mode == "fresh":', "Fresh startup branch missing")
    forbid(worker, 'if args.startup_mode == "fresh":', "Worker bypasses resolved lifecycle decision")

    # Fresh startup is a strict popup-only phase. It owns the complete 60-second
    # watch before control can reach navigation/recovery. GameSession may record
    # the approved startup MAIN invariant, but it must never emit goDown itself.
    require(game_session, "POPUP_WATCH_SECONDS = 60.0", "Fresh popup watch is not fixed at 60 seconds")
    require(game_session, "self._watch_popups(self.POPUP_WATCH_SECONDS)", "Fresh startup does not wait through the popup window")
    require(game_session, "mark_startup_exact_main(", "Fresh startup MAIN invariant marker missing")
    forbid(game_session, "go_down_one_toward_main(", "Fresh popup window must not run goDown recovery")
    forbid(game_session, "farm_boundary_routes", "Fresh popup window must not own boundary navigation")

    # A persisted Pirate Chest prompt is not a generic popup: it cannot be
    # dismissed by X/backdrop and must be completed before farm readiness.
    require(
        pirate_chest,
        "def resume_open_prompt_if_visible(",
        "Pirate Chest has no lifecycle resume entry",
    )
    require(
        game_session,
        "self._resume_pirate_chest_if_visible(",
        "Fresh startup does not prioritize persisted Pirate Chest resume",
    )
    require(
        game_session,
        "before_dismiss=lambda: self._resume_pirate_chest_if_visible(",
        "Pirate Chest cannot preempt generic popup handling during farm entry",
    )
    require(
        popup,
        "before_dismiss: Callable[[], bool] | None = None",
        "Popup loop has no protected-modal handoff",
    )
    require(
        popup,
        "if before_dismiss is not None and before_dismiss():",
        "Generic popup dismissal may steal the Pirate Chest modal",
    )
    require(
        automation,
        "before_dismiss=before_dismiss",
        "Automation facade drops the protected-modal callback",
    )
    require(
        pirate_chest,
        "Pirate chest startup resume closed | proof=own-farm-hud",
        "Startup chest resume does not prove own-farm HUD after closing",
    )

    # Fresh startup alone owns GameSession. Re-entry skips the popup window and
    # only then may use bounded global navigation recovery to prove exact MAIN.
    require(worker, "GameSessionWorkflow(automation).run(timeout=args.timeout)", "Fresh startup workflow missing")
    require(worker, 'function_id="lifecycle_reentry"', "Re-entry RecoveryManager ownership missing")
    require(worker, "recovery.recover_unknown_to_main(", "Re-entry does not use global unknown->MAIN recovery")
    require(worker, 'reason="auto-reentry-existing-client"', "Re-entry recovery reason missing")
    require(worker, "bỏ popup startup 60s", "Re-entry log does not make popup skip explicit")
    require(worker, "AUTO re-entry recovery kết thúc nhưng chưa chứng minh exact-main", "Re-entry exact-MAIN fail-close proof missing")

    # Navigation-only lifecycle recovery must not eagerly resolve an AUTO Builder
    # production Function spec. Production metadata/policy is instantiated only
    # when run_production()/spec is actually requested.
    require(manager, "self._production: ProductionRecovery | None = None", "RecoveryManager production policy is not lazy")
    require(manager, "def production(self) -> ProductionRecovery:", "Lazy ProductionRecovery property missing")
    require(manager, "if self._production is None:", "Lazy ProductionRecovery guard missing")
    require(manager, "self._production = ProductionRecovery(", "ProductionRecovery lazy construction missing")
    require(manager, "return self.production.run_production(", "Production facade no longer resolves lazy policy")
    forbid(manager, "self.production = ProductionRecovery(", "Navigation recovery must not eagerly load production catalog")

    # The public RecoveryManager export is material-aware, so the subclass must
    # preserve the same lazy boundary. Otherwise re-entry still touches the AUTO
    # Builder catalog before navigation recovery starts.
    require(material_recovery, "class MaterialAwareRecoveryManager(BaseRecoveryManager):", "Material-aware manager missing")
    require(material_recovery, "def production(self) -> MaterialAwareProductionRecovery:", "Material-aware production policy is not lazy")
    require(material_recovery, "if self._production is None:", "Material-aware lazy guard missing")
    require(material_recovery, "self._production = MaterialAwareProductionRecovery(", "Material-aware lazy construction missing")
    forbid(material_recovery, "self.production = MaterialAwareProductionRecovery(", "Material-aware manager eagerly loads production catalog")

    print("AUTO MULTI DEV RE-ENTRY LIFECYCLE CONTRACT VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
