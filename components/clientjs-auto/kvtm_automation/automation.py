from __future__ import annotations

from pathlib import Path
import time
from typing import Any

from .actions import (
    AppleJuiceProductionActions,
    AppleSupplyActions,
    AutoVpRecognitionActions,
    BuyingActions,
    CottonPlantingActions,
    FloorNavigationActions,
    FunctionOneNavigationActions,
    FunctionOnePassThreeNavigationActions,
    InventoryActions,
    MachineRepairActions,
    NavigationActions,
    PopupActions,
    PlantingActions,
    ProductionActions,
    SellingActions,
    StallActions,
    YellowFabricProductionActions,
)
from .context import AutomationContext
from .runtime.assets import AssetLibrary
from .runtime.auto_speed_config import AutoSpeedConfig
from .runtime.bootstrap import install_binary_dependencies
from .runtime.driver import ClientJSDriverFactory
from .runtime.resolution import (
    LOGICAL_REFERENCE_SIZE,
    PRODUCTION_CLIENT_SIZE,
    disable_legacy_adaptive_matching,
    ensure_production_client_size,
)
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


def _is_auto_multi_dev_context(context: AutomationContext) -> bool:
    """Scope the 500 production size to AUTO MULTI DEV only.

    KVAutomation is also reusable by diagnostics/other clean workflows. Their
    window-size behavior must not change as a side effect of this migration.
    Multi DEV gives the isolated main worker a stable `auto-multi-dev` work-dir.
    """
    return any(
        str(part).casefold() == "auto-multi-dev"
        for part in Path(context.work_dir).parts
    )


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
        speed_config: AutoSpeedConfig | dict[str, object] | None = None,
    ) -> None:
        self.context = context
        self.speed_config = (
            speed_config
            if isinstance(speed_config, AutoSpeedConfig)
            else AutoSpeedConfig.from_mapping(speed_config)
        )
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
            if _is_auto_multi_dev_context(context):
                context.stage("clientjs-production-resolution-normalizing")
                legacy_disabled = disable_legacy_adaptive_matching()
                if legacy_disabled:
                    context.detail(
                        "AUTO MULTI DEV resolution • legacy adaptive_cv matcher "
                        "đã gỡ trong isolated worker • VisionEngine sở hữu scale"
                    )
                measured = ensure_production_client_size(
                    context.pid,
                    target=PRODUCTION_CLIENT_SIZE,
                )
                context.log(
                    "AUTO MULTI DEV display • production client="
                    f"{measured[0]}x{measured[1]} • logical reference="
                    f"{LOGICAL_REFERENCE_SIZE[0]}x{LOGICAL_REFERENCE_SIZE[1]} • "
                    "resize ổn định trước Bridge V3"
                )
                context.stage("clientjs-production-resolution-ready")

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
        self.planting = PlantingActions(
            context, self.vision, self.wait, self.speed_config
        )
        self.cotton_planting = CottonPlantingActions(
            context, self.vision, self.wait, self.speed_config
        )
        self.floors = FloorNavigationActions(
            context, self.vision, self.wait, self.speed_config
        )
        self.production = ProductionActions(
            context, self.vision, self.wait, self.speed_config
        )
        self.machine_repair = MachineRepairActions(
            context, self.vision, self.wait
        )
        self.apple_supply = AppleSupplyActions(
            context, self.vision, self.wait, self.speed_config
        )
        self.function_one_navigation = FunctionOneNavigationActions(
            context, self.vision, self.wait, self.speed_config
        )
        self.function_one_pass_three_navigation = FunctionOnePassThreeNavigationActions(
            context, self.vision, self.wait, self.speed_config
        )
        self.apple_juice_production = AppleJuiceProductionActions(
            context, self.vision, self.wait, self.speed_config
        )
        self.yellow_fabric_production = YellowFabricProductionActions(
            context, self.vision, self.wait, self.speed_config
        )
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
        self.auto_vp = AutoVpRecognitionActions(
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
