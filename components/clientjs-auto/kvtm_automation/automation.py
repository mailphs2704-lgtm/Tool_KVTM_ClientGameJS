from __future__ import annotations

from pathlib import Path
import threading
import time
from typing import Any

from .actions import (
    BuyingActions,
    InventoryActions,
    NavigationActions,
    PopupActions,
    SellingActions,
    StallActions,
)
from .context import AutomationContext
from .runtime.assets import AssetLibrary
from .runtime.bootstrap import install_binary_dependencies
from .runtime.driver import ClientJSDriverFactory
from .runtime.vision import VisionEngine
from .runtime.wait import Waiter


_IMAGE_RUNTIME_TIMEOUT_SECONDS = 15.0


def _load_image_runtime(context: AutomationContext) -> float:
    """Load native image libraries with a bounded, observable worker thread."""

    started = time.monotonic()
    done = threading.Event()
    failure: list[BaseException] = []

    def run() -> None:
        try:
            install_binary_dependencies(context.auto_root, logger=context.log)
        except BaseException as exc:
            failure.append(exc)
        finally:
            done.set()

    thread = threading.Thread(
        target=run,
        name="kvtm-clean-image-runtime",
        daemon=True,
    )
    thread.start()

    next_heartbeat = 2.0
    while not done.wait(0.10):
        context.ensure_running()
        elapsed = time.monotonic() - started
        if elapsed >= _IMAGE_RUNTIME_TIMEOUT_SECONDS:
            raise RuntimeError(
                "Clean image runtime không sẵn sàng sau "
                f"{_IMAGE_RUNTIME_TIMEOUT_SECONDS:.0f}s; đã hủy thay vì treo vô hạn"
            )
        if elapsed >= next_heartbeat:
            context.log(f"Thư viện ảnh: đang khởi tạo native runtime ({elapsed:.0f}s)")
            next_heartbeat += 2.0

    elapsed = time.monotonic() - started
    if failure:
        raise failure[0]
    return elapsed


class KVAutomation:
    """Clean facade shared by ClientJS workflows.

    DEV may keep the image runtime resident in the same Python process that owns
    the Multi UI. In that mode ``image_runtime_ready=True`` skips all native
    imports here, so a live probe goes directly to the Cocos DLL bridge.
    Production/CLI workers keep the bounded loader as a safe fallback.
    """

    def __init__(
        self,
        context: AutomationContext,
        *,
        driver: Any | None = None,
        image_runtime_ready: bool = False,
    ) -> None:
        self.context = context
        self.component_root = Path(__file__).resolve().parents[1]
        self.driver_factory = ClientJSDriverFactory(
            self.component_root,
            context.auto_root,
        )

        if image_runtime_ready:
            context.stage("clean-image-runtime-ready")
            context.log("Thư viện ảnh: dùng runtime resident của process Multi DEV")
        else:
            context.stage("clean-image-runtime-loading")
            elapsed = _load_image_runtime(context)
            context.log(
                "Thư viện ảnh: toàn bộ runtime READY sau "
                f"{elapsed:.2f}s"
            )
            context.stage("clean-image-runtime-ready")

        if driver is None:
            context.stage("clientjs-dll-bridge-connecting")
            bundle = self.driver_factory.engine(
                context.pid,
                logger=context.log,
            )
            self.driver = bundle.driver
            self.bridge_root = bundle.bridge_root
            self.bridge_mode = bundle.mode
            context.stage("clientjs-dll-bridge-ready")
        else:
            self.driver = driver
            self.bridge_root = Path(".")
            self.bridge_mode = "injected-test-driver"

        self.assets = AssetLibrary.from_package(
            self.component_root,
            context.auto_root,
        )
        self.vision = VisionEngine(self.driver, self.assets)
        self.wait = Waiter(context)

        self.popup = PopupActions(context, self.vision, self.wait)
        self.navigation = NavigationActions(
            context,
            self.vision,
            self.wait,
            self.popup,
        )
        self.stall = StallActions(context, self.vision, self.wait)
        self.inventory = InventoryActions(context, self.vision, self.wait)
        self.buying = BuyingActions(
            context,
            self.vision,
            self.wait,
            self.stall,
        )
        self.selling = SellingActions(
            context,
            self.vision,
            self.wait,
            self.inventory,
        )

    def ensure_main_screen(self, timeout: float = 90.0) -> None:
        self.popup.ensure_main_screen(timeout=timeout)

    def screenshot(self):
        self.context.ensure_running()
        return self.vision.frame()
