from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys


_VENDOR_VERSION = "1"
_VENDOR_PACKAGES = ("numpy", "cv2", "PIL")


def _component_root() -> Path:
    # .../components/clientjs-auto/kvtm_automation/runtime/bootstrap.py
    return Path(__file__).resolve().parents[2]


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
        vendor / "cv2" / "__init__.pyc",
        vendor / "cv2" / "cv2.pyd",
        vendor / "PIL" / "__init__.pyc",
        vendor / "numpy.libs",
    )
    return all(path.exists() for path in required)


def _copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise RuntimeError(f"Thiếu dependency bundle: {source}")
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)


def _materialize_vendor(auto_root: Path, vendor: Path) -> None:
    """Build an isolated third-party cache without exposing legacy business pyc.

    AUTO PRO's PyInstaller extraction splits third-party packages in two:
    pure Python bytecode lives under runtime/pyc while native extensions live
    under _internal.  Adding either parent to sys.path would also expose legacy
    business modules such as automation.pyc/adb_controller.pyc.  Instead we copy
    only NumPy/OpenCV/Pillow into a dedicated vendor directory and import solely
    from that directory.
    """

    root = Path(auto_root).resolve()
    pure_root = root / "runtime" / "pyc"
    native_root = root / "_internal"
    if not pure_root.is_dir() or not native_root.is_dir():
        raise RuntimeError(
            "Thiếu third-party bundle để dựng runtime sạch: "
            f"{pure_root} / {native_root}"
        )

    marker = vendor / ".kvtm-third-party-version"
    try:
        marker.unlink(missing_ok=True)
    except OSError:
        pass

    for package in _VENDOR_PACKAGES:
        destination = vendor / package
        _copy_tree(pure_root / package, destination)
        _copy_tree(native_root / package, destination)

    _copy_tree(native_root / "numpy.libs", vendor / "numpy.libs")
    vendor.mkdir(parents=True, exist_ok=True)
    marker.write_text(_VENDOR_VERSION, encoding="ascii")


def install_binary_dependencies(auto_root: Path) -> None:
    """Expose clean third-party dependencies without importing AUTO PRO logic.

    Only NumPy/OpenCV/Pillow are materialized into components/clientjs-auto/vendor.
    The legacy runtime/pyc and _internal roots are never added to sys.path, so
    automation.pyc, adb_controller.pyc and other AUTO PRO business modules cannot
    be imported through this bootstrap.
    """

    root = Path(auto_root).resolve()
    internal = root / "_internal"
    if not internal.is_dir():
        raise RuntimeError(f"Thiếu thư viện runtime: {internal}")

    vendor = _component_root() / "vendor"
    if not _vendor_is_ready(vendor):
        _materialize_vendor(root, vendor)

    # The isolated vendor must win over arbitrary site-packages so the Python
    # modules and native extensions always come from the same recovered build.
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
            # Native dependencies such as VCRUNTIME may live at _internal root.
            # It is a DLL search directory only; it is never a Python module path.
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

    # NumPy must initialize before cv2 because the OpenCV binding imports
    # numpy.core.multiarray while its extension module is loading.
    import numpy  # noqa: F401
    import cv2  # noqa: F401
    from PIL import Image  # noqa: F401
