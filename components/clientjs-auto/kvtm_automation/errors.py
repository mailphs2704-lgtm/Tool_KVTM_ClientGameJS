class AutomationError(RuntimeError):
    """Base error for the clean KVTM automation runtime."""


class AutomationStopped(InterruptedError):
    """Raised when the owning worker requests a cooperative stop."""


class ClientRestartRequested(AutomationStopped):
    """Raised only at a safe AUTO boundary to ask Multi to restart ClientJS."""


class ScreenTimeout(AutomationError):
    """Raised when an expected visual state is not reached in time."""


class TemplateNotFound(AutomationError):
    """Raised when a required reference asset cannot be resolved."""


class NavigationError(AutomationError):
    """Raised when a navigation state cannot be verified."""


class WrongProductionMachine(NavigationError):
    """A production panel opened, but it belongs to a different machine/floor."""


class ProductSearchExhausted(WrongProductionMachine):
    """The requested product was not found after two bounded page searches."""


class FunctionRestartRequested(AutomationError):
    """Exact MAIN is restored and AUTO Main must restart the current Function."""


class LevelUpPopupDetected(FunctionRestartRequested):
    """Cooperative guard found the blocking level-up reward popup."""


class TransactionError(AutomationError):
    """Raised when a purchase/resale action cannot be verified safely."""


class InventoryFull(TransactionError):
    """The clone warehouse cannot accept more purchased VP."""


class NoEmptyStallSlot(TransactionError):
    """The clone has no empty own-stall slot for another batch of ten VP."""


class InsufficientBatch(TransactionError):
    """The selected VP exists but the game does not expose an active x10 sale option."""
