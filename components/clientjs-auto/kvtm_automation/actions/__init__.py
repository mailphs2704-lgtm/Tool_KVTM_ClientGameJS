from .warehouse_full_guard import install_warehouse_full_guard

install_warehouse_full_guard()

from .apple_supply import AppleSupplyActions
from .buying import BuyingActions
from .dried_tea_production import DriedTeaProductionActions
from .farm_routes import FarmBoundaryRouteActions, FarmRouteActions, NavigationEvidence
from .floor_navigation import FloorMoveResult, FloorNavigationActions
from .function_one_navigation import FunctionOneNavigationActions
from .function_one_pass_three_navigation import FunctionOnePassThreeNavigationActions
from .inventory import InventoryActions
from .item_recognition import AutoVpRecognitionActions, AutoVpSpec, VpRecognition
from .material_shortage_production import (
    MaterialAwareAppleJuiceProductionActions as AppleJuiceProductionActions,
    MaterialAwareCottonPlantingActions as CottonPlantingActions,
    MaterialAwareMachineRepairActions as MachineRepairActions,
    MaterialAwareProductionActions as ProductionActions,
    MaterialAwareProductionResult,
    MaterialAwareYellowFabricProductionActions as YellowFabricProductionActions,
)
from .machine_repair import MachineRepairHandoff
from .navigation import NavigationActions
from .popup import PopupActions
from .planting import PlantingActions, PlantingSegmentResult
from .production import ProductionResult
from .production_panel import ProductionPanelActions
from .rose_oil_production import RoseOilProductionActions
from .selling import SellingActions
from .stall import StallActions
from .vp_sale_transaction import AutoSaleAttempt, VpSaleTransactionActions

__all__ = [
    "AppleJuiceProductionActions",
    "AppleSupplyActions",
    "AutoSaleAttempt",
    "BuyingActions",
    "CottonPlantingActions",
    "DriedTeaProductionActions",
    "FarmBoundaryRouteActions",
    "FarmRouteActions",
    "FloorMoveResult",
    "FloorNavigationActions",
    "FunctionOneNavigationActions",
    "FunctionOnePassThreeNavigationActions",
    "NavigationEvidence",
    "InventoryActions",
    "AutoVpRecognitionActions",
    "AutoVpSpec",
    "VpRecognition",
    "MachineRepairActions",
    "MachineRepairHandoff",
    "MaterialAwareProductionResult",
    "NavigationActions",
    "PopupActions",
    "PlantingActions",
    "PlantingSegmentResult",
    "ProductionActions",
    "ProductionPanelActions",
    "ProductionResult",
    "RoseOilProductionActions",
    "SellingActions",
    "StallActions",
    "VpSaleTransactionActions",
    "YellowFabricProductionActions",
]
