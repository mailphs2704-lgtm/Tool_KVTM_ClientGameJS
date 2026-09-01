from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
import sys
import threading
import time
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

    Transaction-capable clean automation always uses :class:`CocosBridgeDriver`,
    which talks directly to ``kvtm_bridge.dll``. The plain Windows driver is
    retained only as a read-only diagnostic fallback and never carries Dọn quầy
    touches.
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
    ) -> DriverBundle:
        """Connect the native Cocos bridge before loading image dependencies."""
        if logger is not None:
            logger("DLL bridge: bắt đầu kết nối trực tiếp ClientJS")
        driver = CocosBridgeDriver(
            int(pid),
            self.auto_root,
            reference_size=(1000, 1000),
            logger=logger,
        )
        if logger is not None:
            logger("DLL bridge: transport đã sẵn sàng; đang nạp thư viện ảnh")

        started = time.monotonic()
        heartbeat_stop = threading.Event()
        heartbeat = None
        if logger is not None:
            def report_loading() -> None:
                while not heartbeat_stop.wait(5.0):
                    logger(
                        "Thư viện ảnh: vẫn đang nạp "
                        f"({time.monotonic() - started:.0f}s)"
                    )

            heartbeat = threading.Thread(
                target=report_loading,
                name="kvtm-clean-image-runtime-heartbeat",
                daemon=True,
            )
            heartbeat.start()
        try:
            install_binary_dependencies(self.auto_root)
        finally:
            heartbeat_stop.set()
            if heartbeat is not None:
                heartbeat.join(timeout=0.2)

        if logger is not None:
            logger(
                "DLL bridge: thư viện ảnh đã sẵn sàng sau "
                f"{time.monotonic() - started:.1f}s"
            )
        return DriverBundle(
            driver=driver,
            bridge_root=self.auto_root / "bin",
            mode="cocos-dll-direct",
        )
