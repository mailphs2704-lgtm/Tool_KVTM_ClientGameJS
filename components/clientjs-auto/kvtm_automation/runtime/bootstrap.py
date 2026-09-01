from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys


_VENDOR_VERSION = "2"


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

    # A partial cache must never survive a failed materialization. The cache is
    # runtime-only and intentionally lives outside the repository/package.
    if vendor.exists():
        shutil.rmtree(vendor, ignore_errors=True)
    vendor.mkdir(parents=True, exist_ok=True)

    # NumPy: Python package from runtime/pyc + native extensions from _internal.
    _copy_tree(pure_root / "numpy", vendor / "numpy")
    _copy_tree(native_root / "numpy", vendor / "numpy")
    _copy_tree(native_root / "numpy.libs", vendor / "numpy.libs")

    # OpenCV: the PyInstaller extraction already contains a complete cv2 package.
    _copy_tree(native_root / "cv2", vendor / "cv2")

    # Pillow: Python package + native imaging extensions.
    _copy_tree(pure_root / "PIL", vendor / "PIL")
    _copy_tree(native_root / "PIL", vendor / "PIL")

    (vendor / ".kvtm-third-party-version").write_text(
        _VENDOR_VERSION,
        encoding="ascii",
    )


def install_binary_dependencies(auto_root: Path) -> None:
    """Expose clean third-party dependencies without AUTO PRO business logic.

    Only NumPy/OpenCV/Pillow are materialized into a LOCALAPPDATA runtime cache.
    AUTO PRO's runtime/pyc and _internal roots are never added to sys.path, so
    automation.pyc, adb_controller.pyc and other recovered business modules are
    not part of the Dọn quầy execution path.
    """

    root = Path(auto_root).resolve()
    internal = root / "_internal"
    if not internal.is_dir():
        raise RuntimeError(f"Thiếu thư viện runtime: {internal}")

    vendor = _vendor_root()
    if not _vendor_is_ready(vendor):
        _materialize_vendor(root, vendor)

    # The isolated vendor must win over arbitrary site-packages so Python code
    # and native extensions always come from the same recovered build.
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
            # Runtime DLLs such as VCRUNTIME may live here. This is a DLL search
            # directory only and is never a Python module search path.
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

    # NumPy must initialize before cv2 because OpenCV imports
    # numpy.core.multiarray while loading its native extension.
    import numpy  # noqa: F401
    import cv2  # noqa: F401
    from PIL import Image  # noqa: F401
