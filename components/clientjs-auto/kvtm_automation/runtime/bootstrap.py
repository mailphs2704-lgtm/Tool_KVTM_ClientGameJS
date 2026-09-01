from __future__ import annotations

import os
from pathlib import Path
import shutil
import struct
import sys
from typing import Callable


_VENDOR_VERSION = "2"
_SUPPORTED_PYTHON = (3, 11)


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


def _vendor_root() -> Path:
    """Return a persistent runtime cache outside the source/package tree."""

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data)
    else:
        base = Path.home() / ".kvtm"
    return base / "KVTM Multi" / "clean-runtime-vendor" / f"v{_VENDOR_VERSION}"


def _vendor_is_ready(vendor: Path) -> bool:
    marker = vendor / ".kvtm-third-party-version"
    try:
        if marker.read_text(encoding="ascii").strip() != _VENDOR_VERSION:
            return False
    except OSError:
        return False
    required = (
        vendor / "numpy" / "__init__.pyc",
        vendor / "numpy" / "core" / "multiarray.pyc",
        vendor / "numpy" / "_core",
        vendor / "numpy.libs",
        vendor / "cv2" / "__init__.py",
        vendor / "cv2" / "cv2.pyd",
        vendor / "PIL" / "Image.pyc",
        vendor / "PIL" / "_imaging.cp311-win_amd64.pyd",
    )
    return all(path.exists() for path in required)


def _copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise RuntimeError(f"Thiếu dependency bundle: {source}")
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)


def _materialize_vendor(auto_root: Path, vendor: Path) -> None:
    """Build an isolated cache containing third-party libraries only.

    The recovered AUTO PRO bundle stores NumPy and Pillow Python bytecode under
    runtime/pyc while their native extensions live under _internal. OpenCV is a
    complete package under _internal/cv2. The two legacy parent directories are
    never exposed through sys.path; only the selected third-party packages are
    copied into this cache.
    """

    root = Path(auto_root).resolve()
    pure_root = root / "runtime" / "pyc"
    native_root = root / "_internal"
    if not pure_root.is_dir() or not native_root.is_dir():
        raise RuntimeError(
            "Thiếu third-party bundle để dựng runtime sạch: "
            f"{pure_root} / {native_root}"
        )

    if vendor.exists():
        shutil.rmtree(vendor, ignore_errors=True)
    vendor.mkdir(parents=True, exist_ok=True)

    _copy_tree(pure_root / "numpy", vendor / "numpy")
    _copy_tree(native_root / "numpy", vendor / "numpy")
    _copy_tree(native_root / "numpy.libs", vendor / "numpy.libs")
    _copy_tree(native_root / "cv2", vendor / "cv2")
    _copy_tree(pure_root / "PIL", vendor / "PIL")
    _copy_tree(native_root / "PIL", vendor / "PIL")

    (vendor / ".kvtm-third-party-version").write_text(
        _VENDOR_VERSION,
        encoding="ascii",
    )


def install_binary_dependencies(
    auto_root: Path,
    *,
    logger: Callable[[str], None] | None = None,
) -> None:
    """Expose clean third-party dependencies without AUTO PRO business logic.

    ``logger`` is deliberately optional so package/build preflight stays simple,
    while live workers can report exactly which native import is in progress.
    """

    def log(message: str) -> None:
        if logger is None:
            return
        try:
            logger(str(message))
        except Exception:
            pass

    _require_supported_python()
    log(
        "Thư viện ảnh: process "
        f"Python={sys.version.split()[0]} exe={sys.executable} cwd={Path.cwd()}"
    )

    root = Path(auto_root).resolve()
    internal = root / "_internal"
    if not internal.is_dir():
        raise RuntimeError(f"Thiếu thư viện runtime: {internal}")

    vendor = _vendor_root()
    if not _vendor_is_ready(vendor):
        log(f"Thư viện ảnh: dựng vendor cache tại {vendor}")
        _materialize_vendor(root, vendor)
    else:
        log(f"Thư viện ảnh: vendor cache sẵn sàng tại {vendor}")

    vendor_text = str(vendor)
    if vendor_text in sys.path:
        sys.path.remove(vendor_text)
    sys.path.insert(0, vendor_text)

    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        candidates = (
            vendor,
            vendor / "cv2",
            vendor / "numpy.libs",
            vendor / "PIL",
            internal,
        )
        handles = getattr(install_binary_dependencies, "_dll_handles", None)
        if handles is None:
            handles = []
            install_binary_dependencies._dll_handles = handles
        known = {str(getattr(handle, "path", "")) for handle in handles}
        for directory in candidates:
            if not directory.is_dir() or str(directory) in known:
                continue
            try:
                handle = os.add_dll_directory(str(directory))
                handles.append(handle)
            except OSError:
                continue

    log("Thư viện ảnh: import numpy...")
    import numpy  # noqa: F401
    log(f"Thư viện ảnh: numpy READY {getattr(numpy, '__version__', '?')}")

    log("Thư viện ảnh: import cv2...")
    import cv2  # noqa: F401
    log(f"Thư viện ảnh: cv2 READY {getattr(cv2, '__version__', '?')}")

    log("Thư viện ảnh: import PIL...")
    from PIL import Image  # noqa: F401
    log("Thư viện ảnh: PIL READY")
