from __future__ import annotations

from .auto_main_selling import AutoMainSellingActions, AutoSaleAttempt


__all__ = ["VpSaleTransactionActions", "AutoSaleAttempt"]


class VpSaleTransactionActions(AutoMainSellingActions):
    """Generic one-listing VP sale transaction facade.

    Historical code named this behavior ``AutoMainSellingActions`` even though it
    does not own AUTO Main scheduling. The canonical name now reflects its real
    responsibility: verify/open one empty slot, select allowed VP from storage 2,
    prove exact x10, place the listing and verify own-stall state afterwards.

    View iteration, gold/QC order, Function boundaries and Scheduler behavior
    remain outside this Action.
    """
