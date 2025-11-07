"""pytest-xdist-load-testing: Load testing scheduler for pytest-xdist."""

from .api import stop_load_testing, weight
from .concurrent_fixtures import SharedJson, shared_json_fixture_factory

__version__ = "0.1.0"
__all__ = [
    "weight",
    "stop_load_testing",
    "shared_json_fixture_factory",
    "SharedJson",
]
