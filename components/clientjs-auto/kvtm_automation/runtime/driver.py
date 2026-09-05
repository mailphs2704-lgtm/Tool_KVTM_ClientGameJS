from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
import sys
from typing import Any, Callable

from .bootstrap import install_binary_dependencies
from .cocos_bridge import CocosBridgeDriver


@dataclass(frozen=True)
class DriverBundle:
    driver: Any
    bridge_root: Path
    mode: str


class ClientJSDriverFactory:
    """Construct ClientJS drivers for clean automation.

    Transaction-capable clean automation always sends touches through
    :class:`CocosBridgeDriver` and ``kvtm_bridge.dll``. Capture is negotiated
    from the bridge PING response: CAPTURE1 uses DLL shared memory; older bridge
    binaries use the same Win32 capture fallback as the working AUTO.

    Image dependencies are prepared by :class:`KVAutomation` before the DLL
    bridge is connected. The transport path therefore never performs heavy
    native Python imports after a successful bridge PING.
    """

    def __init__(self, component_root: Path, auto_root: Path) -> None:
        self.component_root = Path(component_root).resolve()
        self.auto_root = Path(auto_root).resolve()

    def _pc_driver_root(self) -> Path:
        candidates = (
            self.component_root / "bridge",
            self.auto_root,
        )
        for root in candidates:
            if (root / "pc_driver.py").is_file():
                return root
        raise RuntimeError("Thiếu pc_driver.py cho diagnostic capture")

    def _load_pc_driver(self) -> tuple[Any, Path]:
        install_binary_dependencies(self.auto_root)
        root = self._pc_driver_root()
        text = str(root)
        if text not in sys.path:
            sys.path.insert(0, text)
        return importlib.import_module("pc_driver"), root

    def raw(self, pid: int) -> DriverBundle:
        pc_driver, root = self._load_pc_driver()
        return DriverBundle(
            driver=pc_driver.PCDriver(int(pid), reference_size=(1000, 1000)),
            bridge_root=root,
            mode="pc-window-diagnostic",
        )

    def engine(
        self,
        pid: int,
        *,
        logger: Callable[[str], None] | None = None,
        profile_id: str | None = None,
        profile_file: Path | None = None,
    ) -> DriverBundle:
        """Connect Cocos touch transport and negotiate capture capability."""

        if logger is not None:
            logger("DLL bridge: bắt đầu kết nối trực tiếp ClientJS")
        driver = CocosBridgeDriver(
            int(pid),
            self.auto_root,
            reference_size=(1000, 1000),
            logger=logger,
            profile_id=profile_id,
            profile_file=profile_file,
        )
        mode = (
            "cocos-dll-shared-capture"
            if driver.shared_capture_supported
            else "cocos-dll-touch-win32-capture"
        )
        if logger is not None:
            logger(
                "DLL bridge: transport sẵn sàng; image runtime đã nạp trước; "
                f"mode={mode}"
            )
        return DriverBundle(
            driver=driver,
            bridge_root=self.auto_root / "bin",
            mode=mode,
        )
