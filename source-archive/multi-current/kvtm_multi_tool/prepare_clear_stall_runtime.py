from __future__ import annotations

from pathlib import Path
import sys
import threading
import time
import traceback


def _runtime_paths() -> tuple[Path, Path]:
    multi_root = Path(__file__).resolve().parent
    package_root = multi_root.parent
    component_root = package_root / "components" / "clientjs-auto"
    auto_root = package_root / "AUTO_PRO"
    return component_root, auto_root


def main() -> int:
    component_root, auto_root = _runtime_paths()
    if not component_root.is_dir():
        print(f"[CLEAN RUNTIME] ERROR: missing component root: {component_root}", flush=True)
        return 2
    if not auto_root.is_dir():
        print(f"[CLEAN RUNTIME] ERROR: missing AUTO_PRO root: {auto_root}", flush=True)
        return 2

    component_text = str(component_root)
    if component_text not in sys.path:
        sys.path.insert(0, component_text)

    print("[CLEAN RUNTIME] Preparing Dọn quầy image runtime before Multi starts...", flush=True)
    print(f"[CLEAN RUNTIME] component={component_root}", flush=True)
    print(f"[CLEAN RUNTIME] auto_root={auto_root}", flush=True)

    started = time.monotonic()
    finished = threading.Event()
    failure: list[BaseException] = []

    def run() -> None:
        try:
            from kvtm_automation.runtime.bootstrap import install_binary_dependencies

            install_binary_dependencies(auto_root)
        except BaseException as exc:  # diagnostics must keep the original failure
            failure.append(exc)
        finally:
            finished.set()

    worker = threading.Thread(
        target=run,
        name="kvtm-clean-runtime-prewarm",
        daemon=True,
    )
    worker.start()

    last_report = -5
    while not finished.wait(0.25):
        elapsed = int(time.monotonic() - started)
        if elapsed >= last_report + 5:
            print(
                f"[CLEAN RUNTIME] still preparing image libraries... {elapsed}s",
                flush=True,
            )
            last_report = elapsed

    elapsed = time.monotonic() - started
    if failure:
        exc = failure[0]
        print(
            f"[CLEAN RUNTIME] ERROR after {elapsed:.1f}s: {type(exc).__name__}: {exc}",
            flush=True,
        )
        traceback.print_exception(type(exc), exc, exc.__traceback__)
        return 1

    import cv2
    import numpy
    from PIL import Image  # noqa: F401

    print(
        "[CLEAN RUNTIME] READY "
        f"after {elapsed:.1f}s | cv2={cv2.__version__} | numpy={numpy.__version__}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
