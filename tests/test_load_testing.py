"""Tests for pytest-xdist-load-testing plugin."""
import pytest
from pytest_load_testing.api import weight
from pytest_load_testing.scheduler import LoadTestScheduler


def test_weight_decorator():
    """Test that the weight decorator properly sets the weight marker."""
    @weight(5)
    def test_func():
        pass

    # The weight decorator now returns a pytest marker
    assert hasattr(test_func, 'pytestmark')
    # Check that it's a weight marker with value 5
    markers = test_func.pytestmark if isinstance(test_func.pytestmark, list) else [test_func.pytestmark]  # type: ignore[attr-defined]
    weight_markers = [m for m in markers if m.name == 'weight']
    assert len(weight_markers) == 1
    assert weight_markers[0].args == (5,)


def test_weight_decorator_default():
    """Test that tests without weight decorator have default weight of 1."""
    def test_func():
        pass

    assert not hasattr(test_func, '__pytest_weight__')


def test_weighted_tests_basic(pytester):
    """Test basic weighted test execution."""
    pytester.makepyfile("""
        from pytest_load_testing import weight, stop_load_testing

        @weight(1)
        def test_low_weight():
            assert True

        @weight(10)
        def test_high_weight():
            assert True

        def test_default_weight(request):
            stop_load_testing(request, "Test complete")
            assert True
    """)

    result = pytester.runpytest('--load-test', '-n', '2', '-v')
    # Verify load testing stopped gracefully
    result.stdout.fnmatch_lines([
        '*Interrupted: Test complete*',
    ])
    # Load test mode exits with code 2 (interrupted) when stopped gracefully
    assert result.ret == pytest.ExitCode.INTERRUPTED


def test_scheduler_add_node(pytester):
    """Test adding nodes to the scheduler."""
    pytester.makepyfile("""
        def test_dummy():
            pass
    """)
    config = pytester.parseconfigure("--tx", "2*popen")

    scheduler = LoadTestScheduler(config, None)

    # Create a mock node
    class MockNode:
        shutting_down = False
        def send_runtest_some(self, indices):
            pass
        def shutdown(self):
            pass

    node = MockNode()
    scheduler.add_node(node) # pyright: ignore

    assert node in scheduler.node2pending
    assert scheduler.node2pending[node] == []


def test_scheduler_with_weights(pytester):
    """Test that scheduler respects test weights from runtime data."""
    pytester.makepyfile("""
        def test_dummy():
            pass
    """)
    config = pytester.parseconfigure("--tx", "2*popen")

    scheduler = LoadTestScheduler(config, None)

    # Set up collection with nodeids
    scheduler.collection = ["test1.py::test_a", "test2.py::test_b"]

    # Initialize weights (starts with default weight of 1)
    scheduler._initialize_weights()
    assert scheduler.weights == [1, 1]

    # Simulate weight updates as tests run and report their weights
    scheduler.update_weight("test1.py::test_a", 5)
    scheduler.update_weight("test2.py::test_b", 10)

    # Weights should be updated
    assert len(scheduler.weights) == 2
    assert scheduler.weights == [5, 10]


def test_plugin_integration(pytester):
    """Test full plugin integration with pytest."""
    pytester.makepyfile("""
        from pytest_load_testing import weight, stop_load_testing

        @weight(2)
        def test_weighted():
            assert True

        def test_normal(request):
            stop_load_testing(request, "Test complete")
            assert True
    """)

    result = pytester.runpytest('--load-test', '-n', '2', '-v')
    # Verify load testing stopped gracefully
    result.stdout.fnmatch_lines([
        '*Interrupted: Test complete*',
    ])
    # Load test mode exits with code 2 (interrupted) when stopped gracefully
    assert result.ret == pytest.ExitCode.INTERRUPTED


def test_multiple_weighted_tests(pytester):
    """Test multiple tests with different weights."""
    pytester.makepyfile("""
        from pytest_load_testing import weight, stop_load_testing

        @weight(1)
        def test_weight_1():
            assert True

        @weight(5)
        def test_weight_5():
            assert True

        @weight(10)
        def test_weight_10():
            assert True

        def test_no_weight(request):
            stop_load_testing(request, "Test complete")
            assert True
    """)

    result = pytester.runpytest('--load-test', '-n', '2', '-v')
    # Load test mode exits with code 2 (interrupted) when stopped gracefully
    assert result.ret == pytest.ExitCode.INTERRUPTED




def test_weight_with_parametrize(pytester):
    """Test that weight decorator works with parametrized tests."""
    pytester.makepyfile("""
        import pytest
        from pytest_load_testing import weight, stop_load_testing

        @weight(3)
        @pytest.mark.parametrize("value", [1, 2, 3])
        def test_parametrized(value, request):
            assert value > 0
            if value == 3:
                stop_load_testing(request, "Test complete")
    """)

    result = pytester.runpytest('--load-test', '-n', '2', '-v')
    # Verify load testing stopped gracefully
    result.stdout.fnmatch_lines([
        '*Interrupted: Test complete*',
    ])
    # Load test mode exits with code 2 (interrupted) when stopped gracefully
    assert result.ret == pytest.ExitCode.INTERRUPTED


def test_scheduler_remove_node(pytester):
    """Test removing nodes from the scheduler."""
    pytester.makepyfile("""
        def test_dummy():
            pass
    """)
    config = pytester.parseconfigure("--tx", "2*popen")

    scheduler = LoadTestScheduler(config, None)

    # Create a mock node
    class MockNode:
        shutting_down = False
        def send_runtest_some(self, indices):
            pass
        def shutdown(self):
            pass

    node = MockNode()
    scheduler.add_node(node)
    assert node in scheduler.node2pending

    scheduler.remove_node(node)
    assert node not in scheduler.node2pending


def test_load_test_option(pytester):
    """Test the --load-test command line option."""
    pytester.makepyfile("""
        from pytest_load_testing import stop_load_testing

        def test_simple(request):
            stop_load_testing(request, "Test complete")
            assert True
    """)

    result = pytester.runpytest('--load-test', '-n', '2', '-v')
    # Load test mode exits with code 2 (interrupted) when stopped gracefully
    assert result.ret == pytest.ExitCode.INTERRUPTED


def test_help_message(pytester):
    """Test that help message includes load testing options."""
    result = pytester.runpytest('--help')
    result.stdout.fnmatch_lines([
        '*xdist-load-testing:*',
        '*--load-test*Enable load testing mode*',
    ])


def test_stop_load_testing_does_not_fail_test(pytester):
    """Test that stop_load_testing does not mark the test as failed."""
    pytester.makepyfile("""
        from pytest_load_testing import stop_load_testing

        def test_graceful_stop(request):
            # This test should PASS, not fail
            stop_load_testing(request, "Graceful stop requested")
            assert True  # This assertion should still pass
    """)

    result = pytester.runpytest('--load-test', '-n', '2', '-v')
    # Test should pass, not fail
    result.stdout.fnmatch_lines([
        '*PASSED*test_graceful_stop*',
    ])
    # Session is interrupted (exit code 2) but test passed
    assert result.ret == pytest.ExitCode.INTERRUPTED
    # Verify the interruption message
    result.stdout.fnmatch_lines([
        '*Interrupted: Graceful stop requested*',
    ])


def test_stop_load_testing_with_session(pytester):
    """Test that stop_load_testing works with session.shouldstop."""
    pytester.makepyfile("""
        from pytest_load_testing import stop_load_testing

        def test_first():
            assert True

        def test_stop(request):
            stop_load_testing(request, "Stopping after this test")
            assert True
    """)

    result = pytester.runpytest('--load-test', '-n', '2', '-v')
    # Verify it stopped gracefully
    assert result.ret == pytest.ExitCode.INTERRUPTED
    result.stdout.fnmatch_lines([
        '*Interrupted: Stopping after this test*',
    ])


