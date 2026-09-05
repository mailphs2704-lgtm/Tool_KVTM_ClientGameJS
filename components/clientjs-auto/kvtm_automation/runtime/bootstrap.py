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

    This deliberately mirrors the environment setup used by the working
    ``install_headless_clientjs_runtime`` path.  It reuses only third-party
    NumPy/OpenCV/Pillow files and native DLL directories already synchronized
    by the package build. No files are copied and no AUTO PRO business module
    is imported when the worker starts.

    One subtle but important compatibility detail is the import order.  The
    working AUTO path reaches OpenCV first (through its image stack), and OpenCV
    then resolves NumPy.  Earlier clean builds imported NumPy directly first;
    that path hung on the user's Windows runtime even though CI passed.  Clean
    Dọn quầy therefore follows the proven OpenCV-first order.
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
        "Thư viện ảnh: process "
        f"Python={sys.version.split()[0]} exe={sys.executable} cwd={Path.cwd()}"
    )
    log("Thư viện ảnh: dùng đúng layout + import order của AUTO chính")

    # Match AUTO worker PATH behavior exactly: prepend, do not reconstruct a
    # second vendor tree and do not change cwd behind the worker's back.
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
        # This is intentionally byte-for-byte equivalent in ordering semantics
        # to auto_worker.install_headless_clientjs_runtime(): each path is
        # inserted at index 0 in the same loop order.
        for directory in runtime_paths:
            if directory.exists():
                sys.path.insert(0, str(directory))

        # Package data/native extensions are synchronized once by [1] build.
        # Never import local_launcher here: it performs file copies and loads
        # the legacy AUTO PRO GUI/business modules.
        log("Thư viện ảnh: runtime đóng gói sẵn READY; không copy lại")

        # IMPORTANT: OpenCV first.  The working AUTO path reaches cv2 before it
        # ever performs a standalone ``import numpy``.  cv2 itself resolves the
        # bundled NumPy runtime.  Do not reverse this order without a live test.
        log("Thư viện ảnh: import cv2 theo đúng AUTO chính...")
        cv2 = importlib.import_module("cv2")
        log(
            "Thư viện ảnh: cv2 READY "
            f"{getattr(cv2, '__version__', '?')} source={_module_file(cv2)}"
        )

        log("Thư viện ảnh: xác nhận numpy do cv2/runtime đã nạp...")
        numpy = importlib.import_module("numpy")
        log(
            "Thư viện ảnh: numpy READY "
            f"{getattr(numpy, '__version__', '?')} source={_module_file(numpy)}"
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
        # Third-party modules are resident.  Restore the clean import surface so
        # workflow code cannot later import AUTO PRO business bytecode by name.
        sys.path[:] = previous_sys_path
