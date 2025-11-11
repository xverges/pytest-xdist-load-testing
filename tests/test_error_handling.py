"""Tests for error detection and session stopping."""

import textwrap

import pytest


def test_error_in_setup_stops_session(pytester, run_with_timeout):
    """Test that an error during setup phase stops the load testing session."""
    pytester.makepyfile(
        test_module=textwrap.dedent(
            """
            import pytest

            @pytest.fixture
            def broken_fixture():
                raise RuntimeError("Setup error")

            def test_with_broken_fixture(broken_fixture):
                assert True
            """
        )
    )

    result = run_with_timeout(pytester, "--load-test", "-n", "2", "test_module.py")

    # Should detect error and stop
    result.stdout.fnmatch_lines(
        [
            "*Stopping Load Test: error detected in*during setup phase*",
        ]
    )


@pytest.mark.skip("Exceptions during teardown do not seem to be detected")
def test_error_in_teardown_stops_session(pytester, run_with_timeout):
    """Test that an error during teardown phase stops the load testing session."""
    pytester.makepyfile(
        test_module=textwrap.dedent(
            """
            import pytest

            @pytest.fixture
            def fixture_with_broken_teardown():
                yield "value"
                raise RuntimeError("Teardown error")

            def test_with_broken_teardown(fixture_with_broken_teardown):
                assert True
            """
        )
    )

    result = run_with_timeout(pytester, "--load-test", "-n", "2", "test_module.py", "-vv", timeout=3)

    # Should detect error and stop
    result.stdout.fnmatch_lines(
        [
            "*Stopping Load Test: error detected in*during teardown phase*",
        ]
    )


@pytest.mark.skip("Exceptions during a test result in a failure")
def test_error_in_call_stops_session(pytester, run_with_timeout):
    """Test that an error during call phase stops the load testing session."""
    pytester.makepyfile(
        test_module=textwrap.dedent(
            """
            def test_with_error_1():
                # This will cause an error, not a failure
                a = 1/ 0
                raise RuntimeError("Runtime error")

            def test_with_failure():
                assert False
            """
        )
    )

    result = run_with_timeout(pytester, "--load-test", "-n", "2", "test_module.py", "-vv", "--tb", "native", timeout=1)

    # Should detect error and stop
    result.stdout.fnmatch_lines(
        [
            "*Stopping Load Test: error detected in*during call phase*",
        ]
    )


def test_multiple_tests_one_with_error(pytester, run_with_timeout):
    """Test that session stops when one test has an error, even with other passing tests."""
    pytester.makepyfile(
        test_module=textwrap.dedent(
            """
            import pytest

            def test_passing():
                assert True

            @pytest.fixture
            def broken_fixture():
                raise RuntimeError("Setup error")

            def test_with_error(broken_fixture):
                assert True
            """
        )
    )

    result = run_with_timeout(pytester, "--load-test", "-n", "2", "test_module.py", "-vv")

    # Should detect error and stop
    result.stdout.fnmatch_lines(
        [
            "*Stopping Load Test: error detected in*",
        ]
    )
    assert result.ret != 0
