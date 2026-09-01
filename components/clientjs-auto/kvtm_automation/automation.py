from __future__ import annotations

from pathlib import Path
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
from .runtime.driver import ClientJSDriverFactory
from .runtime.vision import VisionEngine
from .runtime.wait import Waiter


class KVAutomation:
    """Clean facade shared by all ClientJS automation workflows.

    This is the standalone replacement for the role previously played by
    AUTO PRO's FarmAutomation/ADBController pair. It is intentionally small:
    reusable mechanics live in `actions/`, while business flows live in
    `workflows/`.
    """

    def __init__(
        self,
        context: AutomationContext,
        *,
        driver: Any | None = None,
    ) -> None:
        self.context = context
        self.component_root = Path(__file__).resolve().parents[1]
        self.driver_factory = ClientJSDriverFactory(
            self.component_root,
            context.auto_root,
        )
        if driver is None:
            context.stage("clientjs-engine-connecting")
            bundle = self.driver_factory.engine(context.pid)
            self.driver = bundle.driver
            self.bridge_root = bundle.bridge_root
            self.bridge_mode = bundle.mode
            context.stage("clientjs-engine-ready")
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
