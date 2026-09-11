from __future__ import annotations

from .farm_routes import FarmRouteActions, NavigationEvidence


__all__ = ["FunctionOneNavigationActions", "NavigationEvidence"]
FILE_FUNCTIONS = (
    "LEGACY compatibility alias cho FarmRouteActions",
    "Không sở hữu route implementation hoặc tọa độ/swipe riêng",
    "Code mới phải dùng farm_routes/FarmRouteActions",
)


class FunctionOneNavigationActions(FarmRouteActions):
    """Deprecated compatibility wrapper over canonical FarmRouteActions."""
