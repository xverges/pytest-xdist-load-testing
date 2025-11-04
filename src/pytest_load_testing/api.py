"""Public API for pytest-xdist-load-testing."""
import pytest

from .constants import LOAD_TEST_STOP_SIGNAL


def weight(value: int):
    """
    Decorator to set the weight of a test for load testing.

    Args:
        value: The weight of the test (higher = more likely to be selected)

    Example:
        @weight(5)
        def test_important():
            pass

        # Or use pytest marker directly:
        @pytest.mark.weight(5)
        def test_important():
            pass
    """
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"Weight must be a positive integer, got {value}")
    return pytest.mark.weight(value)


def stop_load_testing(
    request: pytest.FixtureRequest,
    message: str = "Test requested stop"
):
    """
    Function to stop the load testing scheduler gracefully.

    This sets session.shouldstop to signal pytest to stop the test session
    without marking the current test as failed. This is the preferred way
    to stop load testing when a condition is met.

    Args:
        request: The pytest request fixture (required)
        message: The reason for stopping the load testing

    Example:
        from pytest_load_testing import stop_load_testing

        def test_something(request):
            if some_condition:
                stop_load_testing(request, "Stopping due to condition")
    """
    request.session.shouldstop = message
    request.node.user_properties.append((LOAD_TEST_STOP_SIGNAL, message))

