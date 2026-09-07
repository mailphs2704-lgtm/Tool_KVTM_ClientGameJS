"""Shared clean runtime used by AUTO MULTI DEV and Dọn quầy development.

This package is intentionally independent from AUTO PRO business modules.
"""

from .image_runtime import install_binary_dependencies

__all__ = ["install_binary_dependencies"]
