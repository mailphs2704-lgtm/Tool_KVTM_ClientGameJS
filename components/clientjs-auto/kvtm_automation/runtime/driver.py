from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
import sys
from typing import Any

from .bootstrap import install_binary_dependencies


@dataclass(frozen=True)
class DriverBundle:
    driver: Any
    bridge_root: Path
    mode: str


class ClientJSDriverFactory:
    """Construct the clean PC/engine bridge without AUTO PRO automation.pyc."""

    def __init__(self, component_root: Path, auto_root: Path) -> None:
        self.component_root = Path(component_root).resolve()
        self.auto_root = Path(auto_root).resolve()

    def _bridge_root(self) -> Path:
        candidates = (
            self.component_root / "bridge",
            self.auto_root,
        )
        for root in candidates:
            if (
                (root / "pc_driver.py").is_file()
                and (root / "engine_driver.py").is_file()
                and (root / "adaptive_cv.py").is_file()
            ):
                return root
        raise RuntimeError(
            "Thiếu bridge source sạch (pc_driver.py/engine_driver.py/adaptive_cv.py)"
        )

    def _load_bridge_modules(self) -> tuple[Any, Any, Path]:
        install_binary_dependencies(self.auto_root)
        root = self._bridge_root()
        text = str(root)
        if text not in sys.path:
            sys.path.insert(0, text)
        pc_driver = importlib.import_module("pc_driver")
        engine_driver = importlib.import_module("engine_driver")
        return pc_driver, engine_driver, root

    def raw(self, pid: int) -> DriverBundle:
        pc_driver, _engine_driver, root = self._load_bridge_modules()
        return DriverBundle(
            driver=pc_driver.PCDriver(int(pid), reference_size=(1000, 1000)),
            bridge_root=root,
            mode="pc-window",
        )

    def engine(self, pid: int) -> DriverBundle:
        _pc_driver, engine_driver, root = self._load_bridge_modules()
        return DriverBundle(
            driver=engine_driver.EngineDriver(int(pid), reference_size=(1000, 1000)),
            bridge_root=root,
            mode="cocos-engine",
        )
