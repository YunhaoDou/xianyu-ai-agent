"""Platform adapter module: abstract platform interface and Xianyu adapter."""

from .adapter import PlatformAdapter, PlatformEvent
from .xianyu import XianyuAdapter

__all__ = ["PlatformAdapter", "PlatformEvent", "XianyuAdapter"]
