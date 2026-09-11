from __future__ import annotations

from .function_one_navigation import FunctionOneNavigationActions, NavigationEvidence
from .function_one_pass_three_navigation import FunctionOnePassThreeNavigationActions


__all__ = [
    "FarmRouteActions",
    "FarmBoundaryRouteActions",
    "NavigationEvidence",
]


class FarmRouteActions(FunctionOneNavigationActions):
    """Generic reusable farm route composer over canonical floor primitives.

    The historical implementation lived in ``FunctionOneNavigationActions``.
    New AUTO code must depend on this generic name because the same verified
    routes are shared by Function 1, Function 2, recipes and Global Recovery.
    The legacy class remains only as a compatibility base until all external
    imports have migrated.
    """


class FarmBoundaryRouteActions(FunctionOnePassThreeNavigationActions):
    """Generic boundary-aware farm routes shared by recipes and recovery.

    This includes goDown boundary proof and the verified XUỐNG-button route.
    The historical Function-1 class remains a compatibility base only.
    """
