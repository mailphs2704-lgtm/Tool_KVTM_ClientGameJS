from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import struct
import sys
import time


_DLL_HANDLES: list[object] = []


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KVTM Dọn quầy standalone full-resale worker")
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--profile-file", required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--profile-name", required=True)
    parser.add_argument("--friend-ordinal", type=int, required=True)
    parser.add_argument("--stall-id", type=int, required=True)
    parser.add_argument("--quantity", type=int, required=True)
    parser.add_argument("--max-stall-passes", type=int, default=10)
    parser.add_argument("--allowed-items-json", default="[]")
    parser.add_argument("--drag-speed", type=float, default=0.35)
    parser.add_argument("--work-dir", required=True)
    return parser


def _module_path(module) -> Path:
    value = getattr(module, "__file__", None)
    if not value:
        raise RuntimeError(f"Không xác định được nguồn module {module!r}")
    return Path(value).resolve()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _install_dll_dirs(*directories: Path) -> None:
    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return
    known = {
        os.path.normcase(os.path.abspath(str(getattr(handle, "path", ""))))
        for handle in _DLL_HANDLES
    }
    for directory in directories:
        if not directory.is_dir():
            continue
        key = os.path.normcase(os.path.abspath(str(directory)))
        if key in known:
            continue
        try:
            _DLL_HANDLES.append(os.add_dll_directory(str(directory)))
            known.add(key)
        except OSError:
            pass


def _install_unicode_safe_imwrite(cv2, emit) -> None:
    """Make OpenCV image writes safe for Vietnamese Windows paths.

    ``cv2.imwrite`` can return ``False`` when the target path contains Unicode
    characters even though the frame itself is valid. Encode in memory and let
    Python write the bytes so the shared Dọn quầy runtime can keep its existing
    ``cv2.imwrite`` contract without changing AUTO MULTI DEV source.
    """
    current = cv2.imwrite
    if getattr(current, "_kvtm_unicode_safe", False):
        return

    def unicode_safe_imwrite(filename, image, params=None):
        try:
            target = Path(os.fspath(filename))
            suffix = target.suffix or ".png"
            encode_params = [] if params is None else list(params)
            ok, encoded = cv2.imencode(suffix, image, encode_params)
            if not ok:
                return False
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(encoded.tobytes())
            return True
        except Exception:
            return False

    unicode_safe_imwrite._kvtm_unicode_safe = True
    cv2.imwrite = unicode_safe_imwrite
    emit(
        "probe_boot",
        stage="standalone-unicode-imwrite-ready",
        writer="cv2.imencode+Path.write_bytes",
    )


def _install_transient_capture_retry(auto_root: Path, emit) -> None:
    """Retry only the strict Bridge V3 writer-map startup race.

    A ready PING can precede publication of the writer-specific CAPTURE3 shared
    mapping by a short interval. The packaged driver intentionally refuses HWND
    fallback; keep that contract and simply repeat the same strict screenshot
    call for the exact transient WinError 2 condition.
    """
    engine_driver = importlib.import_module("engine_driver")
    source = _module_path(engine_driver)
    root = Path(auto_root).resolve()
    if not _inside(source, root):
        raise RuntimeError(f"engine_driver không được nạp từ AUTO_PRO: {source}")

    EngineDriver = getattr(engine_driver, "EngineDriver")
    original = EngineDriver.screenshot
    if getattr(original, "_kvtm_standalone_capture_retry", False):
        return

    waits = (0.15, 0.30, 0.60, 1.00)

    def is_transient(exc: BaseException) -> bool:
        text = str(exc)
        return "Bridge V3 capture thất bại" in text and "[WinError 2]" in text

    def screenshot_with_retry(self, *args, **kwargs):
        try:
            return original(self, *args, **kwargs)
        except RuntimeError as exc:
            if not is_transient(exc):
                raise
            last_error = exc

        for attempt, delay in enumerate(waits, 1):
            emit(
                "probe_progress",
                message=(
                    "Bridge V3 capture transient WinError 2 • "
                    f"retry {attempt}/{len(waits)} sau {delay:.2f}s"
                ),
            )
            time.sleep(delay)
            try:
                return original(self, *args, **kwargs)
            except RuntimeError as exc:
                if not is_transient(exc):
                    raise
                last_error = exc

        raise last_error

    screenshot_with_retry._kvtm_standalone_capture_retry = True
    EngineDriver.screenshot = screenshot_with_retry
    emit(
        "probe_boot",
        stage="standalone-capture-retry-ready",
        retries=len(waits),
        waits_seconds=list(waits),
        strict_bridge_only=True,
        hwnd_fallback=False,
    )


def _bootstrap_standalone_image_runtime(auto_root: Path, emit) -> None:
    """Preload the packaged image stack without the unverified cv2-first route.

    The shared clean bootstrap currently imports Pillow -> cv2 -> NumPy. Live
    standalone evidence on Windows/CPython 3.11 shows that route can block
    inside the cv2 import. For the standalone tool we keep the same packaged
    AUTO_PRO files and DLL directories but make NumPy resident before OpenCV,
    then hand the already-loaded image runtime to the shared Dọn quầy workflow.
    """
    if tuple(sys.version_info[:2]) != (3, 11) or struct.calcsize("P") * 8 != 64:
        raise RuntimeError(
            "Dọn quầy standalone yêu cầu CPython 3.11 64-bit; "
            f"đang chạy {sys.version.split()[0]} ({sys.executable})"
        )

    root = Path(auto_root).resolve()
    pyc = root / "runtime" / "pyc"
    internal = root / "_internal"
    if not pyc.is_dir() or not internal.is_dir():
        raise RuntimeError(f"Thiếu packaged image runtime: {pyc} / {internal}")

    emit(
        "probe_boot",
        stage="standalone-image-runtime-start",
        import_order="PIL_NUMPY_CV2",
    )
    emit(
        "probe_progress",
        message=(
            "Standalone image runtime: packaged AUTO_PRO • "
            "đổi bootstrap sang PIL -> NumPy -> cv2"
        ),
    )

    os.environ["PATH"] = os.pathsep.join((
        str(internal),
        str(root / "platform-tools"),
        os.environ.get("PATH", ""),
    ))
    _install_dll_dirs(
        internal,
        internal / "cv2",
        internal / "numpy.libs",
        internal / "pywin32_system32",
        internal / "Pythonwin",
    )

    previous_sys_path = list(sys.path)
    try:
        # Match the proven local launcher search surface: PYC, _internal, then
        # pywin32 subfolders. auto_root is already present in previous_sys_path.
        for directory in (pyc, internal):
            sys.path.insert(0, str(directory))
        for directory in (
            internal / "win32",
            internal / "win32" / "lib",
            internal / "Pythonwin",
            internal / "pywin32_system32",
        ):
            if directory.exists():
                sys.path.insert(0, str(directory))

        emit("probe_progress", message="Standalone image runtime: preload PIL._imaging...")
        PIL = importlib.import_module("PIL")
        Image = importlib.import_module("PIL.Image")
        importlib.import_module("PIL._imaging")
        emit(
            "probe_progress",
            message=(
                "Standalone image runtime: PIL READY "
                f"source={_module_path(PIL)} image={_module_path(Image)}"
            ),
        )

        emit(
            "probe_progress",
            message="Standalone image runtime: import numpy trước cv2...",
        )
        numpy = importlib.import_module("numpy")
        emit(
            "probe_progress",
            message=(
                "Standalone image runtime: numpy READY "
                f"{getattr(numpy, '__version__', '?')} source={_module_path(numpy)}"
            ),
        )

        emit(
            "probe_progress",
            message="Standalone image runtime: import cv2 sau numpy resident...",
        )
        cv2 = importlib.import_module("cv2")
        emit(
            "probe_progress",
            message=(
                "Standalone image runtime: cv2 READY "
                f"{getattr(cv2, '__version__', '?')} source={_module_path(cv2)}"
            ),
        )
        _install_unicode_safe_imwrite(cv2, emit)

        for name, module in (("PIL", PIL), ("numpy", numpy), ("cv2", cv2)):
            source = _module_path(module)
            if not _inside(source, root):
                raise RuntimeError(
                    f"{name} không được nạp từ AUTO_PRO packaged runtime: {source}"
                )
    finally:
        sys.path[:] = previous_sys_path

    emit(
        "probe_boot",
        stage="standalone-image-runtime-ready",
        import_order="PIL_NUMPY_CV2",
        image_runtime_ready=True,
    )


def main() -> int:
    args = _parser().parse_args()
    runtime_root = Path(args.runtime_root).resolve()
    worker_dir = runtime_root / "components" / "clientjs-auto" / "worker"
    component_dir = runtime_root / "components" / "clientjs-auto"
    auto_root = runtime_root / "AUTO_PRO"
    for path in (worker_dir, component_dir, auto_root):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)

    os.environ["KVTM_MULTI_PROFILE_FILE"] = str(Path(args.profile_file).resolve())
    os.environ["KVTM_SKIP_RUNTIME_SYNC"] = "1"

    from clean_worker_support import StopChannel, configure_utf8_stdio, emit

    configure_utf8_stdio()
    try:
        _bootstrap_standalone_image_runtime(auto_root, emit)
        _install_transient_capture_retry(auto_root, emit)
    except Exception as exc:
        emit("probe_error", error=f"Standalone runtime bootstrap lỗi: {exc}")
        return 3

    from clear_stall_probe_runtime import ProbeConfig, run_probe

    try:
        allowed = json.loads(args.allowed_items_json)
        if not isinstance(allowed, list):
            raise ValueError("allowed-items-json phải là list")
    except (json.JSONDecodeError, ValueError) as exc:
        emit("probe_error", error=str(exc))
        return 2

    quantity = int(args.quantity)
    if quantity < 10 or quantity > 1000 or quantity % 10:
        emit("probe_error", error="Số lượng Dọn quầy phải là bội số 10 trong 10..1000")
        return 2
    purchase_limit = quantity // 10

    channel = StopChannel()
    channel.start()
    config = ProbeConfig(
        auto_root=auto_root,
        pid=int(args.pid),
        profile_id=str(args.profile_id),
        profile_name=str(args.profile_name),
        friend_ordinal=int(args.friend_ordinal),
        resale_storage_id=int(args.stall_id),
        buy_quantity=quantity,
        work_dir=Path(args.work_dir),
        purchase_limit=purchase_limit,
        max_stall_passes=int(args.max_stall_passes),
        resale_batch_limit=purchase_limit,
        allowed_item_ids=tuple(str(x) for x in allowed),
        clear_stall_drag_speed=float(args.drag_speed),
    )
    return run_probe(
        config,
        emit_event=lambda payload: emit(
            str(payload.get("event") or "probe_progress"),
            **{key: value for key, value in payload.items() if key != "event"},
        ),
        stop_event=channel.event,
        image_runtime_ready=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
