"""Compatibility facade for the shared ClientJS clean image runtime.

The implementation lives outside ``kvtm_automation`` so AUTO MULTI DEV and
Dọn quầy development can reuse one technical bootstrap without importing or
modifying AUTO PRO business modules.
"""

from shared_runtime.image_runtime import install_binary_dependencies

__all__ = ["install_binary_dependencies"]
