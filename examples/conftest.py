"""Conftest for examples to ensure fixtures work with xdist."""

from pytest_load_testing.concurrent_fixtures import shared_json_fixture_factory

# Re-export the fixture so it's available in examples
__all__ = ["shared_json_fixture_factory"]
