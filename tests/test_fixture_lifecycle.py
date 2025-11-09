"""
Tests for fixture lifecycle in load testing mode.
"""

import pytest


def test_request_fixture_available(pytester):
    """
    Test that the request fixture is available on each test execution.

    This verifies the fix for the KeyError: 'request' issue that occurred
    when tests were re-run in load testing mode.
    """
    pytester.makepyfile("""
        import pytest
        from pytest_load_testing import weight, stop_load_testing

        count = 0

        @weight(1)
        def test_request_fixture_available(request):
            global count

            # The request fixture should be available
            assert request is not None
            assert hasattr(request, 'node')
            assert hasattr(request, 'session')

            if count < 5:
                count += 1
            else:
              stop_load_testing(request, "Request fixture verified")
    """)

    result = pytester.runpytest("--load-test", "-n", "2", "-v")

    # Should stop gracefully
    result.stdout.fnmatch_lines(
        [
            "*Interrupted: Request fixture verified*",
        ]
    )
    assert result.ret == pytest.ExitCode.INTERRUPTED


def test_all_fixture_scopes(pytester):
    """Test that fixtures with different scopes provide correct data."""
    pytester.makepyfile("""
        import pytest
        import json
        from pathlib import Path
        from filelock import FileLock
        from pytest_load_testing import weight, stop_load_testing

        @pytest.fixture(scope="session")
        def fixture_counts(tmp_path_factory):
            counts_file = tmp_path_factory.mktemp("data") / "fixture_counts.json"
            lock_file = counts_file.with_suffix('.lock')

            with FileLock(str(lock_file)):
                if not counts_file.exists():
                    counts_file.write_text(json.dumps({
                        "session_setup": 0, "session_teardown": 0,
                        "module_setup": 0, "module_teardown": 0,
                        "function_setup": 0, "function_teardown": 0,
                    }))

            class Counter:
                def __init__(self, file_path, lock_path):
                    self.file = file_path
                    self.lock = lock_path

                def increment(self, key):
                    with FileLock(str(self.lock)):
                        data = json.loads(self.file.read_text())
                        data[key] += 1
                        self.file.write_text(json.dumps(data))
                        return data[key]

                def read(self):
                    with FileLock(str(self.lock)):
                        return json.loads(self.file.read_text())

            counter = Counter(counts_file, lock_file)
            yield counter

            # Write final counts for verification
            Path("fixture_counts.json").write_text(json.dumps(counter.read()))

        @pytest.fixture(scope="session")
        def execution_counts(tmp_path_factory):
            counts_file = tmp_path_factory.mktemp("data") / "execution_counts.json"
            lock_file = counts_file.with_suffix('.lock')

            with FileLock(str(lock_file)):
                if not counts_file.exists():
                    counts_file.write_text(json.dumps({"test1": 0, "test2": 0}))

            class Counter:
                def __init__(self, file_path, lock_path):
                    self.file = file_path
                    self.lock = lock_path

                def increment(self, key):
                    with FileLock(str(self.lock)):
                        data = json.loads(self.file.read_text())
                        data[key] += 1
                        self.file.write_text(json.dumps(data))
                        return data

            return Counter(counts_file, lock_file)

        @pytest.fixture(scope="session")
        def session_fixture(fixture_counts):
            setup_count = fixture_counts.increment("session_setup")
            fixture_data = {"scope": "session", "data": "session_data", "setup_count": setup_count}
            yield fixture_data
            fixture_counts.increment("session_teardown")

        @pytest.fixture(scope="module")
        def module_fixture(fixture_counts):
            setup_count = fixture_counts.increment("module_setup")
            fixture_data = {"scope": "module", "data": "module_data", "setup_count": setup_count}
            yield fixture_data
            fixture_counts.increment("module_teardown")

        @pytest.fixture(scope="function")
        def function_fixture(fixture_counts):
            setup_count = fixture_counts.increment("function_setup")
            fixture_data = {"scope": "function", "data": "function_data", "setup_count": setup_count}
            yield fixture_data
            fixture_counts.increment("function_teardown")

        @weight(1)
        def test_all_fixture_scopes(request, session_fixture, module_fixture, function_fixture, fixture_counts, execution_counts):
            data = execution_counts.increment("test1")
            execution_count_test1 = data["test1"]
            execution_count_test2 = data["test2"]

            # Verify fixtures provide expected data
            assert session_fixture["scope"] == "session"
            assert session_fixture["data"] == "session_data"
            assert module_fixture["scope"] == "module"
            assert module_fixture["data"] == "module_data"
            assert function_fixture["scope"] == "function"
            assert function_fixture["data"] == "function_data"

            # Session and module fixtures should be setup exactly once
            assert session_fixture["setup_count"] == 1, f"Session fixture setup {session_fixture['setup_count']} times, expected 1"
            assert module_fixture["setup_count"] == 1, f"Module fixture setup {module_fixture['setup_count']} times, expected 1"

            # Module and session should not be torn down yet
            counts = fixture_counts.read()
            assert counts["module_teardown"] == 0, f"Module fixture torn down {counts['module_teardown']} times, expected 0"
            assert counts["session_teardown"] == 0, f"Session fixture torn down {counts['session_teardown']} times, expected 0"

            # Stop after both tests have run at least 3 times each
            if execution_count_test1 >= 3 and execution_count_test2 >= 3:
                stop_load_testing(request, f"All fixture scopes verified (test1: {execution_count_test1}, test2: {execution_count_test2})")

        @weight(1)
        def test_function_fixture_reinitialization(request, function_fixture, execution_counts):
            data = execution_counts.increment("test2")
            execution_count_test1 = data["test1"]
            execution_count_test2 = data["test2"]

            # Verify function fixture provides expected data
            assert function_fixture["scope"] == "function"
            assert function_fixture["data"] == "function_data"
            assert function_fixture["setup_count"] > 0

            # Stop after both tests have run at least 3 times each
            if execution_count_test1 >= 3 and execution_count_test2 >= 3:
                stop_load_testing(request, f"All fixture scopes verified (test1: {execution_count_test1}, test2: {execution_count_test2})")
    """)

    result = pytester.runpytest("--load-test", "-n", "1", "-v")

    # Should stop gracefully
    result.stdout.fnmatch_lines(
        [
            "*Interrupted: All fixture scopes verified (test1: *, test2: *)*",
        ]
    )
    assert result.ret == pytest.ExitCode.INTERRUPTED

    # Verify from outside pytester that session and module fixtures were torn down exactly once
    import json

    fixture_counts_file = pytester.path / "fixture_counts.json"
    assert fixture_counts_file.exists(), "fixture_counts.json should exist after test completion"

    counts = json.loads(fixture_counts_file.read_text())
    assert counts["session_setup"] == 1, f"Session fixture should be setup exactly once, got {counts['session_setup']}"
    assert counts["session_teardown"] == 1, (
        f"Session fixture should be torn down exactly once, got {counts['session_teardown']}"
    )
    assert counts["module_setup"] == 1, f"Module fixture should be setup exactly once, got {counts['module_setup']}"
    assert counts["module_teardown"] == 1, (
        f"Module fixture should be torn down exactly once, got {counts['module_teardown']}"
    )
    # Function fixture should be setup/torn down for both tests (at least 6 times total: 3 per test)
    assert counts["function_setup"] >= 6, (
        f"Function fixture should be setup at least 6 times, got {counts['function_setup']}"
    )
    assert counts["function_teardown"] >= 6, (
        f"Function fixture should be torn down at least 6 times, got {counts['function_teardown']}"
    )
