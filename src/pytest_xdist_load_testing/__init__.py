"""pytest-xdist-load-testing: Load testing scheduler for pytest-xdist."""

from .api import stop_load_testing, weight

__version__ = "0.2.3"
__all__ = [
    "weight",
    "stop_load_testing",
]
