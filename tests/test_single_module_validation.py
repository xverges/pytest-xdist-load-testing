"""Tests for single module validation in load testing mode."""

import pytest


def test_single_module_accepted(pytester, run_with_timeout):
    """Test that load testing works with a single module."""
    pytester.makepyfile("""
        from pytest_xdist_load_testing import stop_load_testing

        def test_one(request):
            stop_load_testing(request, "Test complete")
            assert True

        def test_two():
            assert True
    """)

    result = run_with_timeout(pytester, "--load-test", "-n", "2")
    # Should run successfully and stop gracefully
    result.stdout.fnmatch_lines(
        [
            "*Interrupted: Test complete*",
        ]
    )
    assert result.ret == pytest.ExitCode.INTERRUPTED


def test_multiple_modules_rejected(pytester, run_with_timeout):
    """Test that load testing rejects multiple modules."""
    # Create two test files
    pytester.makepyfile(
        test_module1="""
        def test_in_module1():
            assert True
    """
    )

    pytester.makepyfile(
        test_module2="""
        def test_in_module2():
            assert True
    """
    )

    # Try to run both modules
    result = run_with_timeout(pytester, "--load-test", "-n", "2", "test_module1.py", "test_module2.py")

    # Should fail with error message about multiple modules
    result.stdout.fnmatch_lines(
        [
            "*Load testing requires tests from a single module only*",
            "*Found tests from 2 different modules*",
        ]
    )
    # Should mention both modules
    assert "test_module1.py" in result.stdout.str()
    assert "test_module2.py" in result.stdout.str()


def test_multiple_modules_in_directory_rejected(pytester, run_with_timeout):
    """Test that load testing rejects when discovering multiple modules."""
    # Create two test files in the same directory
    pytester.makepyfile(
        test_a="""
        def test_a():
            assert True
    """
    )

    pytester.makepyfile(
        test_b="""
        def test_b():
            assert True
    """
    )

    # Try to run all tests in directory (will discover both)
    result = run_with_timeout(pytester, "--load-test", "-n", "2")

    # Should fail with error message about multiple modules
    result.stdout.fnmatch_lines(
        [
            "*Load testing requires tests from a single module only*",
            "*Found tests from 2 different modules*",
        ]
    )


def test_single_module_with_classes(pytester, run_with_timeout):
    """Test that load testing works with test classes in a single module."""
    pytester.makepyfile("""
        from pytest_xdist_load_testing import stop_load_testing

        class TestClassA:
            def test_one(self):
                assert True

            def test_two(self):
                assert True

        class TestClassB:
            def test_three(self, request):
                stop_load_testing(request, "Test complete")
                assert True
    """)

    result = run_with_timeout(pytester, "--load-test", "-n", "2")
    # Should run successfully - all tests are in the same module
    result.stdout.fnmatch_lines(
        [
            "*Interrupted: Test complete*",
        ]
    )
    assert result.ret == pytest.ExitCode.INTERRUPTED
