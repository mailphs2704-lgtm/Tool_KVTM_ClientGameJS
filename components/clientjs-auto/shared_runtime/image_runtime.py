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
    current = tuple(sys.version_info[:2])
    if current != _SUPPORTED_PYTHON:
        raise RuntimeError(
            "ClientJS clean runtime yêu cầu CPython 3.11 x64; "
            f"đang chạy Python {current[0]}.{current[1]} ({sys.executable})."
        )
    if struct.calcsize("P") * 8 != 64:
        raise RuntimeError("ClientJS clean runtime yêu cầu CPython 3.11 64-bit")


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
    """Load only packaged third-party image binaries shared by clean workflows.

    AUTO MULTI DEV and Dọn quầy may share this technical runtime, but AUTO PRO
    business modules remain outside this package.  The import order deliberately
    follows the last proven clean order: Pillow native -> OpenCV -> NumPy.
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

    log(
        "Shared image runtime: process "
        f"Python={sys.version.split()[0]} exe={sys.executable} cwd={Path.cwd()}"
    )
    log("Shared image runtime: dùng packaged third-party layout; không gọi local_launcher")

    os.environ["PATH"] = os.pathsep.join((
        str(internal),
        str(root / "platform-tools"),
        os.environ.get("PATH", ""),
    ))
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
        for directory in runtime_paths:
            if directory.exists():
                sys.path.insert(0, str(directory))

        log("Shared image runtime: preload PIL._imaging...")
        PIL = importlib.import_module("PIL")
        Image = importlib.import_module("PIL.Image")
        importlib.import_module("PIL._imaging")
        log(
            "Shared image runtime: PIL READY "
            f"source={_module_file(PIL)} image={_module_file(Image)}"
        )

        log("Shared image runtime: import cv2 sau PIL native...")
        cv2 = importlib.import_module("cv2")
        log(
            "Shared image runtime: cv2 READY "
            f"{getattr(cv2, '__version__', '?')} source={_module_file(cv2)}"
        )

        log("Shared image runtime: xác nhận numpy resident...")
        numpy = importlib.import_module("numpy")
        log(
            "Shared image runtime: numpy READY "
            f"{getattr(numpy, '__version__', '?')} source={_module_file(numpy)}"
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
                "Shared image runtime đã nạp nhầm business module AUTO_PRO: "
                + ", ".join(leaked)
            )
    finally:
        sys.path[:] = previous_sys_path
