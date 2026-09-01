from __future__ import annotations

import os
from pathlib import Path
import sys


def install_binary_dependencies(auto_root: Path) -> None:
    """Expose AUTO PRO's bundled third-party wheels/DLLs without importing its pyc.

    Only the packaged Python libraries (cv2/numpy/PIL/pywin32 dependencies) are
    reused. automation.pyc, adb_controller.pyc and runtime/pyc are deliberately
    not added to sys.path.
    """

    root = Path(auto_root).resolve()
    internal = root / "_internal"
    if not internal.is_dir():
        raise RuntimeError(f"Thiếu thư viện runtime: {internal}")

    # Append, never prepend: the system Python stdlib remains authoritative.
    text = str(internal)
    if text not in sys.path:
        sys.path.append(text)

    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        candidates = (
            internal,
            internal / "cv2",
            internal / "numpy.libs",
            internal / "PIL",
            internal / "pywin32_system32",
            internal / "win32",
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

    # Fail early with the exact dependency that cannot load.
    import cv2  # noqa: F401
    import numpy  # noqa: F401
    from PIL import Image  # noqa: F401
