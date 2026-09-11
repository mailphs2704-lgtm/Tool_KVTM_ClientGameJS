from __future__ import annotations

from .farm_routes import FarmBoundaryRouteActions


__all__ = ["FunctionOnePassThreeNavigationActions"]
FILE_FUNCTIONS = (
    "LEGACY compatibility alias cho FarmBoundaryRouteActions",
    "Không sở hữu boundary route implementation hoặc tọa độ riêng",
    "Code mới phải dùng farm_boundary_routes/FarmBoundaryRouteActions",
)


class FunctionOnePassThreeNavigationActions(FarmBoundaryRouteActions):
    """Deprecated compatibility wrapper over canonical FarmBoundaryRouteActions."""
