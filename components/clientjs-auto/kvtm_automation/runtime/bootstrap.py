from __future__ import annotations

import importlib
import os
from pathlib import Path
import struct
import sys
from typing import Callable


_SUPPORTED_PYTHON = (3, 11)
_FORBIDDEN_BUSINESS_MODULES = (
    "automation",
    "adb_controller",
    "image_processor",
    "gui",
    "gui_base",
)


def _require_supported_python() -> None:
    """Fail fast before loading CPython-3.11 native image extensions."""

    current = tuple(sys.version_info[:2])
    if current != _SUPPORTED_PYTHON:
        raise RuntimeError(
            "Dọn quầy clean yêu cầu CPython 3.11 x64; "
            f"đang chạy Python {current[0]}.{current[1]} ({sys.executable}). "
            "Không nạp native extension cp311 bằng Python 3.12/3.13."
        )
    if struct.calcsize("P") * 8 != 64:
        raise RuntimeError("Dọn quầy clean yêu cầu CPython 3.11 64-bit")


def _module_file(module) -> Path:
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


def _prepend_path_environment(*directories: Path) -> None:
    """Mirror the proven AUTO worker DLL/PATH environment without business imports."""

    current = [item for item in os.environ.get("PATH", "").split(os.pathsep) if item]
    normalized = {os.path.normcase(os.path.abspath(item)) for item in current}
    prefix: list[str] = []
    for directory in directories:
        if not directory.is_dir():
            continue
        text = str(directory)
        key = os.path.normcase(os.path.abspath(text))
        if key in normalized:
            continue
        normalized.add(key)
        prefix.append(text)
    if prefix:
        os.environ["PATH"] = os.pathsep.join(prefix + current)


def _install_dll_directories(*directories: Path) -> None:
    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return

    handles = getattr(_install_dll_directories, "_handles", None)
    if handles is None:
        handles = []
        _install_dll_directories._handles = handles
    known = {
        os.path.normcase(os.path.abspath(str(getattr(handle, "path", ""))))
        for handle in handles
    }
    for directory in directories:
        if not directory.is_dir():
            continue
        text = str(directory)
        key = os.path.normcase(os.path.abspath(text))
        if key in known:
            continue
        try:
            handles.append(os.add_dll_directory(text))
            known.add(key)
        except OSError:
            continue


def install_binary_dependencies(
    auto_root: Path,
    *,
    logger: Callable[[str], None] | None = None,
) -> None:
    """Load only third-party image libraries from AUTO PRO's proven layout.

    The normal AUTO worker is already proven on the user's ClientJS runtime. It
    does not reconstruct NumPy/OpenCV/Pillow into a second cache; instead it
    exposes the extracted PyInstaller ``runtime/pyc`` and ``_internal`` layout,
    configures the Windows DLL search path, then imports the runtime.

    Clean Dọn quầy now mirrors only that *third-party environment setup*. It
    imports NumPy, OpenCV and Pillow, verifies that their files come from the
    packaged AUTO_PRO tree, and restores ``sys.path`` immediately afterwards.
    AUTO PRO business modules such as automation/adb_controller/image_processor
    are never imported by this function.
    """

    def log(message: str) -> None:
        if logger is None:
            return
        try:
            logger(str(message))
        except Exception:
            pass

    _require_supported_python()

    root = Path(auto_root).resolve()
    pyc = root / "runtime" / "pyc"
    internal = root / "_internal"
    if not pyc.is_dir() or not internal.is_dir():
        raise RuntimeError(
            "Thiếu third-party runtime AUTO_PRO: "
            f"{pyc} / {internal}"
        )

    # Clean workers used to inherit cwd=AUTO_PRO while importing a reconstructed
    # vendor cache. The launcher prewarm succeeded from Multi, while the worker
    # hung at ``import numpy``. Keep native imports away from AUTO_PRO's root so
    # Windows current-directory DLL lookup cannot shadow the intended runtime.
    safe_cwd = Path(__file__).resolve().parents[2]
    try:
        os.chdir(safe_cwd)
    except OSError as exc:
        raise RuntimeError(f"Không chuyển được clean runtime cwd tới {safe_cwd}: {exc}") from exc

    log(
        "Thư viện ảnh: process "
        f"Python={sys.version.split()[0]} exe={sys.executable} cwd={Path.cwd()}"
    )
    log("Thư viện ảnh: dùng trực tiếp layout thư viện AUTO chính; không dựng vendor cache")

    # Match the environment used by install_headless_clientjs_runtime(), which
    # is the known-good AUTO path on ClientJS. Only library paths are reused.
    _prepend_path_environment(internal, root / "platform-tools")
    _install_dll_directories(
        internal,
        internal / "cv2",
        internal / "numpy.libs",
        internal / "pywin32_system32",
        internal / "Pythonwin",
    )

    runtime_paths = (
        pyc,
        internal,
        internal / "win32",
        internal / "win32" / "lib",
        internal / "Pythonwin",
        internal / "pywin32_system32",
        root,
    )
    previous_sys_path = list(sys.path)
    business_before = {
        name for name in _FORBIDDEN_BUSINESS_MODULES if name in sys.modules
    }

    try:
        # Intentionally use the same insertion order as the working AUTO worker.
        for directory in runtime_paths:
            if not directory.exists():
                continue
            text = str(directory)
            while text in sys.path:
                sys.path.remove(text)
            sys.path.insert(0, text)

        log("Thư viện ảnh: import numpy từ layout AUTO chính...")
        numpy = importlib.import_module("numpy")
        log(
            "Thư viện ảnh: numpy READY "
            f"{getattr(numpy, '__version__', '?')} source={_module_file(numpy)}"
        )

        log("Thư viện ảnh: import cv2 từ layout AUTO chính...")
        cv2 = importlib.import_module("cv2")
        log(
            "Thư viện ảnh: cv2 READY "
            f"{getattr(cv2, '__version__', '?')} source={_module_file(cv2)}"
        )

        log("Thư viện ảnh: import PIL từ layout AUTO chính...")
        PIL = importlib.import_module("PIL")
        Image = importlib.import_module("PIL.Image")
        log(
            "Thư viện ảnh: PIL READY "
            f"source={_module_file(PIL)} image={_module_file(Image)}"
        )

        for name, module in (("numpy", numpy), ("cv2", cv2), ("PIL", PIL)):
            source = _module_file(module)
            if not _inside(source, root):
                raise RuntimeError(
                    f"{name} không được nạp từ AUTO_PRO packaged runtime: {source}"
                )

        business_after = {
            name for name in _FORBIDDEN_BUSINESS_MODULES if name in sys.modules
        }
        leaked = sorted(business_after - business_before)
        if leaked:
            raise RuntimeError(
                "Clean image bootstrap đã nạp nhầm business module AUTO_PRO: "
                + ", ".join(leaked)
            )
    finally:
        # NumPy/OpenCV/Pillow are now resident. Restore the clean worker import
        # surface so later workflow code cannot accidentally import AUTO PRO's
        # business bytecode by name.
        sys.path[:] = previous_sys_path
