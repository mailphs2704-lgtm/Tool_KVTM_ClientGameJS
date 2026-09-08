from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
import sys
from typing import Any, Callable

from .bootstrap import install_binary_dependencies


@dataclass(frozen=True)
class DriverBundle:
    driver: Any
    bridge_root: Path
    mode: str


class ClientJSDriverFactory:
    """Construct strict Bridge V3 drivers for AUTO MULTI DEV.

    The main Multi Dev automation must negotiate CAPTURE3/INPUT4/BATCH_SWIPE.
    CAPTURE1 and HWND capture are not accepted as silent fallbacks.
    """

    REQUIRED_V3_TOKENS = (
        "KVTM_BRIDGE_V3",
        "CAPTURE3",
        "INPUT4",
        "BATCH_SWIPE",
        "NO_LAYOUT",
        "CAPTURE3_SYNC2",
        "CAPTURE3_FIXEDMAP",
        "CAPTURE3_WRITERMAP2",
    )

    def __init__(self, component_root: Path, auto_root: Path) -> None:
        self.component_root = Path(component_root).resolve()
        self.auto_root = Path(auto_root).resolve()

    def _pc_driver_root(self) -> Path:
        candidates = (self.component_root / "bridge", self.auto_root)
        for root in candidates:
            if (root / "pc_driver.py").is_file():
                return root
        raise RuntimeError("Thiếu pc_driver.py cho diagnostic capture")

    def _load_module(self, name: str):
        install_binary_dependencies(self.auto_root)
        root = self._pc_driver_root()
        root_text = str(root)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)
        return importlib.import_module(name), root

    def raw(self, pid: int) -> DriverBundle:
        pc_driver, root = self._load_module("pc_driver")
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
        """Connect only the packaged Bridge V3 engine transport."""

        if logger is not None:
            logger("DLL bridge V3: bắt đầu kết nối trực tiếp ClientJS")
        engine_driver, root = self._load_module("engine_driver")
        if profile_file is not None:
            engine_driver.PROFILE_FILE = Path(profile_file).resolve()
        if logger is not None:
            logger(f"DLL bridge V3: loader={engine_driver.LOADER}")
            logger(f"DLL bridge V3: dll={engine_driver.BRIDGE}")
        driver = engine_driver.EngineDriver(
            int(pid), reference_size=(1000, 1000)
        )
        response = driver._pipe("PING\n", 1000)
        missing = [token for token in self.REQUIRED_V3_TOKENS if token not in response]
        if missing:
            close_pipe = getattr(driver, "_close_pipe", None)
            if callable(close_pipe):
                close_pipe()
            if (
                "KVTM_BRIDGE_V3" in response
                and any(
                    token in missing
                    for token in (
                        "CAPTURE3_SYNC2",
                        "CAPTURE3_FIXEDMAP",
                        "CAPTURE3_WRITERMAP2",
                    )
                )
            ):
                raise RuntimeError(
                    "ClientJS đang giữ Bridge V3 resident cũ "
                    "(thiếu CAPTURE3_SYNC2/CAPTURE3_FIXEDMAP/CAPTURE3_WRITERMAP2). "
                    "DLL đã inject không thể thay nóng; hãy đóng/mở lại đúng ClientJS "
                    "sau khi build runtime DEV rồi chạy AUTO MULTI DEV lại."
                )
            raise RuntimeError(
                "AUTO MULTI DEV yêu cầu Bridge V3; PING thiếu "
                + ", ".join(missing)
                + f": {response}"
            )
        if logger is not None:
            logger(f"DLL bridge V3: PING sẵn sàng -> {response}")
            logger(
                "DLL bridge V3: transport sẵn sàng; "
                "mode=cocos-dll-v3-batch-swipe-capture3-writermap2"
            )
        return DriverBundle(
            driver=driver,
            bridge_root=root / "bin",
            mode="cocos-dll-v3-batch-swipe-capture3-writermap2",
        )
