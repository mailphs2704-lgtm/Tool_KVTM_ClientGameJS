from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "components/clientjs-auto/worker/auto_multi_dev_worker.py"
HOST = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_host.py"
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

    # Parent lifecycle ownership: a fresh marker exists only when AUTO Main
    # itself had to launch ClientJS. Adopting an already-running ClientJS must
    # not manufacture a fresh-start marker.
    require(host, f'_AUTO_MAIN_FRESH_MARKER = "{MARKER}"', "Host fresh marker name changed")
    require(host, "def _install_auto_main_lifecycle_tracking(dev_entry)", "Host lifecycle tracking missing")
    require(host, "original_start = app_cls._start_clean_auto_session", "AUTO Main start is not tracked")
    require(host, "original_launch = app_cls._launch", "ClientJS launch hook missing")
    require(host, 'self._auto_main_launch_tracking_depth = previous_depth + 1', "AUTO Main launch scope missing")
    require(host, 'if int(getattr(self, "_auto_main_launch_tracking_depth", 0) or 0) <= 0:', "Non-AUTO launches are not excluded")
    require(host, 'marker_root = dev_entry.core.APP_DIR / "auto-multi-dev" / profile_id', "Fresh marker is not profile-scoped")
    require(host, '"pid": int(process.pid)', "Fresh marker does not bind ClientJS PID")
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

    # Fresh startup alone owns the 60-second GameSession popup watch. Re-entry
    # must use the existing bounded global navigation recovery and prove MAIN.
    require(worker, "GameSessionWorkflow(automation).run(timeout=args.timeout)", "Fresh startup workflow missing")
    require(worker, 'function_id="lifecycle_reentry"', "Re-entry RecoveryManager ownership missing")
    require(worker, "recovery.recover_unknown_to_main(", "Re-entry does not use global unknown->MAIN recovery")
    require(worker, 'reason="auto-reentry-existing-client"', "Re-entry recovery reason missing")
    require(worker, "bỏ popup startup 60s", "Re-entry log does not make popup skip explicit")
    require(worker, "AUTO re-entry recovery kết thúc nhưng chưa chứng minh exact-main", "Re-entry exact-MAIN fail-close proof missing")

    print("AUTO MULTI DEV RE-ENTRY LIFECYCLE CONTRACT VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
