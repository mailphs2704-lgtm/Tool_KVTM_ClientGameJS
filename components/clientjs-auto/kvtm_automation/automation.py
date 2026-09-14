from __future__ import annotations

import os
from pathlib import Path
import time
from typing import Callable, Any

from .actions import (
    AppleJuiceProductionActions,
    AppleSupplyActions,
    AutoVpRecognitionActions,
    BuyingActions,
    CottonPlantingActions,
    FarmBoundaryRouteActions,
    FarmRouteActions,
    FloorNavigationActions,
    InventoryActions,
    MachineRepairActions,
    NavigationActions,
    PopupActions,
    PlantingActions,
    ProductionActions,
    RoseOilProductionActions,
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
    NativeCaptureDriver,
    detect_client_resolution,
    disable_legacy_adaptive_matching,
)
from .runtime.vision import VisionEngine
from .runtime.wait import Waiter


_AUTO_MULTI_DEV_FPS_ENV = "KVTM_MULTI_DEV_RENDER_FPS"
_AUTO_MULTI_DEV_FPS_DEFAULT = 20
_AUTO_MULTI_DEV_FPS_CAPABILITY = "FPS_LIMIT1"


def _auto_multi_dev_fps_limit() -> int:
    """Read the Multi DEV host-selected FPS inherited by the isolated worker."""
    raw = os.environ.get(_AUTO_MULTI_DEV_FPS_ENV, str(_AUTO_MULTI_DEV_FPS_DEFAULT))
    try:
        fps = int(raw)
    except (TypeError, ValueError):
        fps = _AUTO_MULTI_DEV_FPS_DEFAULT
    return fps if 5 <= fps <= 120 else _AUTO_MULTI_DEV_FPS_DEFAULT


def _apply_auto_multi_dev_fps_governor(
    driver: Any,
    context: AutomationContext,
) -> None:
    """Confirm the host-selected ClientJS render FPS without changing capture/input."""
    pipe = getattr(driver, "_pipe", None)
    if not callable(pipe):
        context.detail(
            "GPU policy • Bridge V3 không expose pipe trực tiếp • bỏ qua FPS governor"
        )
        return

    protocol = str(pipe("PING\n", 1000))
    if _AUTO_MULTI_DEV_FPS_CAPABILITY not in protocol.split():
        context.detail(
            "GPU policy • Bridge V3 resident chưa có FPS_LIMIT1 • "
            "giữ FPS hiện tại; restart ClientJS sau khi cập nhật để nạp DLL mới"
        )
        return

    fps = _auto_multi_dev_fps_limit()
    response = str(pipe(f"FPS {fps}\n", 1000))
    expected = f"OK FPS {fps}"
    if response != expected:
        raise RuntimeError(
            "Bridge V3 quảng bá FPS_LIMIT1 nhưng không áp dụng được governor: "
            f"{response}"
        )
    context.log(
        f"GPU policy • ClientJS render={fps} FPS qua "
        "Director::setAnimationInterval • target kế thừa từ Multi DEV • "
        "AUTO capture giữ nguyên native size"
    )


def _load_image_runtime(context: AutomationContext) -> float:
    """Load native image libraries on the worker main thread."""
    started = time.monotonic()
    context.log("Thư viện ảnh: cold-load đồng bộ trên worker main thread")
    install_binary_dependencies(context.auto_root, logger=context.log)
    return time.monotonic() - started


def _is_auto_multi_dev_context(context: AutomationContext) -> bool:
    """Scope native-resolution capture ownership to AUTO MULTI DEV only."""
    return any(
        str(part).casefold() == "auto-multi-dev"
        for part in Path(context.work_dir).parts
    )


class KVAutomation:
    """Clean facade shared by ClientJS workflows.

    AUTO MULTI DEV never resizes ClientJS. The physical client size already
    chosen by the user/profile is detected after Bridge V3 attaches. A 500x500
    client selects the native-500 recognition contract; a 1000x1000 client
    selects the native-1000 contract. Business/input coordinates remain logical
    1000x1000 in both modes.
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
        auto_multi_resolution = _is_auto_multi_dev_context(context)
        self.resolution_contract = None

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
            if auto_multi_resolution:
                context.stage("clientjs-resolution-preserve-start")
                legacy_disabled = disable_legacy_adaptive_matching()
                if legacy_disabled:
                    context.detail(
                        "AUTO MULTI DEV resolution • legacy adaptive_cv matcher "
                        "đã gỡ trong isolated worker • VisionEngine sở hữu scale"
                    )

            context.stage("clientjs-dll-bridge-connecting")
            bundle = self.driver_factory.engine(
                context.pid,
                logger=context.detail,
                profile_id=context.profile_id,
                profile_file=context.profile_file,
            )
            self.driver = bundle.driver
            if auto_multi_resolution:
                _apply_auto_multi_dev_fps_governor(self.driver, context)
                contract = detect_client_resolution(self.driver)
                self.resolution_contract = contract
                self.driver = NativeCaptureDriver(
                    self.driver,
                    contract=contract,
                )
                native_probe = self.driver.screenshot(format="opencv")
                native_height, native_width = native_probe.shape[:2]
                context.log(
                    "AUTO MULTI DEV resolution • preserve-client-size • native="
                    f"{native_width}x{native_height} • table="
                    f"{contract.table_size[0]}x{contract.table_size[1]} • "
                    "logical="
                    f"{LOGICAL_REFERENCE_SIZE[0]}x{LOGICAL_REFERENCE_SIZE[1]} • no-resize"
                )
                context.log(
                    "AUTO MULTI DEV capture • native CAPTURE3="
                    f"{native_width}x{native_height} • VisionEngine nhận frame thật • "
                    "không upscale về 1000 trước matching"
                )
                context.stage("clientjs-resolution-preserve-ready")
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

        # Generic shared farm routes are the canonical facade for all Functions,
        # Recipes and Global Recovery. Historical Function-specific attributes are
        # aliases to the same objects so old callers keep working without owning
        # a second route implementation/state.
        self.farm_routes = FarmRouteActions(
            context, self.vision, self.wait, self.speed_config
        )
        self.farm_boundary_routes = FarmBoundaryRouteActions(
            context, self.vision, self.wait, self.speed_config
        )
        self.function_one_navigation = self.farm_routes
        self.function_one_pass_three_navigation = self.farm_boundary_routes

        self.apple_juice_production = AppleJuiceProductionActions(
            context, self.vision, self.wait, self.speed_config
        )
        self.yellow_fabric_production = YellowFabricProductionActions(
            context, self.vision, self.wait, self.speed_config
        )
        self.rose_oil_production = RoseOilProductionActions(
            context, self.vision, self.wait, self.speed_config
        )
        self.navigation = NavigationActions(
            context,
            self.vision,
            self.wait,
            self.popup,
        )
        self.stall = StallActions(context, self.vision, self.wait)
        # Stall geometry/pulse count are independent from timing. Only override
        # the duration selected in the Multi DEV speed dialog, preserving the
        # proven two-swipe route and render settle policy.
        self.stall.swipe_duration = float(self.speed_config.shop_drag_speed)
        context.detail(
            "AUTO MULTI DEV stall speed • "
            f"kéo quầy={self.stall.swipe_duration:.3f}s/swipe • "
            f"settle={self.stall.swipe_settle:.3f}s"
        )
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

    def ensure_main_screen(
        self,
        timeout: float = 90.0,
        *,
        before_dismiss: Callable[[], bool] | None = None,
    ) -> None:
        self.popup.ensure_main_screen(
            timeout=timeout,
            before_dismiss=before_dismiss,
        )

    def screenshot(self):
        self.context.ensure_running()
        return self.vision.frame()
