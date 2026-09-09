from __future__ import annotations

import ctypes
from pathlib import Path
import struct
import sys
import threading
import time
import traceback


_RUNTIME_TIMEOUT_SECONDS = 15.0


def _roots() -> tuple[Path, Path, Path]:
    multi_root = Path(__file__).resolve().parent
    package_root = multi_root.parent
    component_root = package_root / "components" / "clientjs-auto"
    auto_root = package_root / "AUTO_PRO"
    return multi_root, component_root, auto_root


def _check_python() -> None:
    if tuple(sys.version_info[:2]) != (3, 11) or struct.calcsize("P") * 8 != 64:
        raise RuntimeError(
            "KVTM Multi DEV resident host yêu cầu CPython 3.11 x64; "
            f"đang chạy {sys.version.split()[0]} ({sys.executable})"
        )


def _load_resident_runtime(component_root: Path, auto_root: Path) -> None:
    component_text = str(component_root)
    if component_text not in sys.path:
        sys.path.insert(0, component_text)

    from kvtm_automation.runtime.bootstrap import install_binary_dependencies

    print(
        "[KVTM DEV] Resident host: loading image runtime BEFORE importing Multi UI...",
        flush=True,
    )
    started = time.monotonic()
    done = threading.Event()
    failure: list[BaseException] = []

    def log(message: str) -> None:
        print(f"[CLEAN RUNTIME] {message}", flush=True)

    def load() -> None:
        try:
            install_binary_dependencies(auto_root, logger=log)
        except BaseException as exc:
            failure.append(exc)
        finally:
            done.set()

    thread = threading.Thread(
        target=load,
        name="kvtm-dev-resident-host-image-runtime",
        daemon=True,
    )
    thread.start()

    next_heartbeat = 2.0
    while not done.wait(0.10):
        elapsed = time.monotonic() - started
        if elapsed >= _RUNTIME_TIMEOUT_SECONDS:
            raise RuntimeError(
                "Resident host image runtime không sẵn sàng sau "
                f"{_RUNTIME_TIMEOUT_SECONDS:.0f}s"
            )
        if elapsed >= next_heartbeat:
            print(f"[CLEAN RUNTIME] resident host import... {elapsed:.0f}s", flush=True)
            next_heartbeat += 2.0

    if failure:
        raise failure[0]

    import cv2
    import numpy
    from PIL import Image  # noqa: F401

    print(
        "[CLEAN RUNTIME] RESIDENT HOST READY "
        f"after {time.monotonic() - started:.2f}s | "
        f"cv2={cv2.__version__} | numpy={numpy.__version__}",
        flush=True,
    )


def _install_non_modal_error_ui(core) -> None:
    """Keep Multi DEV runtime errors in status/logs instead of modal dialogs.

    Only ``showerror`` is replaced. Informational/confirmation dialogs remain
    available for explicit operator actions. AUTO runtime errors are supervised
    by the isolated worker and should never block all clones behind an OK box.
    """

    def showerror_no_modal(title, message, *args, **kwargs):
        del args, kwargs
        text = str(message).replace("\n", " | ")
        print(f"[KVTM DEV] UI ERROR NON-MODAL | {title}: {text}", flush=True)
        return "ok"

    core.messagebox.showerror = showerror_no_modal
    print(
        "[KVTM DEV] Error UI: messagebox.showerror disabled; status/log recovery enabled",
        flush=True,
    )


def _configure_dpi() -> None:
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def main() -> int:
    try:
        _check_python()
        multi_root, component_root, auto_root = _roots()
        if not component_root.is_dir() or not auto_root.is_dir():
            raise RuntimeError(
                f"Thiếu package runtime: component={component_root} auto={auto_root}"
            )

        # This is the ONLY native image import for the DEV lifetime. The process
        # stays alive afterwards and becomes the Multi UI + probe runtime.
        _load_resident_runtime(component_root, auto_root)

        multi_text = str(multi_root)
        if multi_text not in sys.path:
            sys.path.insert(0, multi_text)

        print("[KVTM DEV] Resident host: importing Multi UI AFTER runtime READY...", flush=True)
        import kvtm_multi_dev_entry
        from auto_builder_integration import install_auto_builder_integration

        # Multi DEV is unattended-capable: error dialogs must never block all
        # running clones. Callers still update note/status and every worker error
        # remains in action/detail logs.
        _install_non_modal_error_ui(kvtm_multi_dev_entry.core)

        # Builder is DEV-only and is layered onto MultiDevApp after import. This
        # keeps the shared kvtm_multi.py production UI untouched while reusing its
        # exact ttk styles/tab strip/lifecycle.
        install_auto_builder_integration(
            kvtm_multi_dev_entry.MultiDevApp,
            kvtm_multi_dev_entry.core,
        )

        _configure_dpi()
        app = kvtm_multi_dev_entry.MultiDevApp()
        app.mainloop()
        return 0
    except Exception as exc:
        print(
            f"[KVTM DEV] RESIDENT HOST FAILED: {type(exc).__name__}: {exc}",
            flush=True,
        )
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
