from __future__ import annotations

from pathlib import Path
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


def _load_image_runtime(context: AutomationContext) -> float:
    """Load native image libraries on the worker main thread.

    Windows native extension initialization can deadlock when cv2/NumPy is
    imported from a temporary background thread. The proven AUTO PRO/package
    path imports these DLLs synchronously. The worker owns the outer watchdog,
    so this function must not create another loader thread.
    """
    started = time.monotonic()
    context.log("Thư viện ảnh: cold-load đồng bộ trên worker main thread")
    install_binary_dependencies(context.auto_root, logger=context.log)
    return time.monotonic() - started



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
                logger=context.detail,
                profile_id=context.profile_id,
                profile_file=context.profile_file,
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
        self.vision = VisionEngine(
            self.driver, self.assets, detail_logger=context.detail
        )
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
