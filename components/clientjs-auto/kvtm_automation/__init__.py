"""Clean, reusable automation runtime for KVTM ClientJS.

This package intentionally does not import AUTO PRO automation.pyc/FarmAutomation.
AUTO PRO remains a behavioral reference and asset/library source only.
"""

from .automation import KVAutomation
from .context import AutomationContext

__all__ = ["AutomationContext", "KVAutomation"]
