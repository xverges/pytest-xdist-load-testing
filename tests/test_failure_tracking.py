"""Tests for failure tracking functionality."""
import time
import pytest


def test_failure_tracking_initialization(pytester):
    """Test that scheduler initializes with empty tracking dictionaries."""
    pytester.makepyfile("""
        def test_dummy():
            pass
    """)
    config = pytester.parseconfigure("--tx", "2*popen")

    from pytest_load_testing.scheduler import LoadTestScheduler
    scheduler = LoadTestScheduler(config, None)

    assert isinstance(scheduler.test_passes, dict)
    assert isinstance(scheduler.test_failures, dict)
    assert isinstance(scheduler.last_success_time, dict)
    assert len(scheduler.test_passes) == 0
    assert len(scheduler.test_failures) == 0
    assert len(scheduler.last_success_time) == 0


def test_mark_test_failed_increments_counter(pytester):
    """Test that marking a test as failed increments its failure counter."""
    pytester.makepyfile("""
        def test_dummy():
            pass
    """)
    config = pytester.parseconfigure("--tx", "2*popen")

    from pytest_load_testing.scheduler import LoadTestScheduler
    scheduler = LoadTestScheduler(config, None)
    scheduler.collection = ["test_example.py::test_one"]

    # Mark test as failed
    scheduler.mark_test_failed("test_example.py::test_one")

    assert scheduler.test_failures["test_example.py::test_one"] == 1

    # Mark same test as failed again
    scheduler.mark_test_failed("test_example.py::test_one")

    assert scheduler.test_failures["test_example.py::test_one"] == 2


def test_mark_test_passed_increments_counter(pytester):
    """Test that marking a test as passed increments its pass counter."""
    pytester.makepyfile("""
        def test_dummy():
            pass
    """)
    config = pytester.parseconfigure("--tx", "2*popen")

    from pytest_load_testing.scheduler import LoadTestScheduler
    scheduler = LoadTestScheduler(config, None)
    scheduler.collection = ["test_example.py::test_one"]

    # Mark test as passed
    scheduler.mark_test_passed("test_example.py::test_one")

    assert scheduler.test_passes["test_example.py::test_one"] == 1

    # Mark same test as passed again
    scheduler.mark_test_passed("test_example.py::test_one")

    assert scheduler.test_passes["test_example.py::test_one"] == 2


def test_mark_test_passed_updates_last_success_time(pytester):
    """Test that marking a test as passed updates its last success timestamp."""
    pytester.makepyfile("""
        def test_dummy():
            pass
    """)
    config = pytester.parseconfigure("--tx", "2*popen")

    from pytest_load_testing.scheduler import LoadTestScheduler
    scheduler = LoadTestScheduler(config, None)
    scheduler.collection = ["test_example.py::test_one"]

    # Get time before marking as passed
    before_time = time.time()

    # Mark test as passed
    scheduler.mark_test_passed("test_example.py::test_one")

    # Get time after marking as passed
    after_time = time.time()

    # Verify timestamp is within expected range
    assert "test_example.py::test_one" in scheduler.last_success_time
    timestamp = scheduler.last_success_time["test_example.py::test_one"]
    assert before_time <= timestamp <= after_time


def test_multiple_tests_tracked_independently(pytester):
    """Test that multiple tests are tracked independently."""
    pytester.makepyfile("""
        def test_dummy():
            pass
    """)
    config = pytester.parseconfigure("--tx", "2*popen")

    from pytest_load_testing.scheduler import LoadTestScheduler
    scheduler = LoadTestScheduler(config, None)
    scheduler.collection = [
        "test_example.py::test_one",
        "test_example.py::test_two",
        "test_example.py::test_three"
    ]

    # Mark different tests with different outcomes
    scheduler.mark_test_passed("test_example.py::test_one")
    scheduler.mark_test_passed("test_example.py::test_one")
    scheduler.mark_test_failed("test_example.py::test_two")
    scheduler.mark_test_passed("test_example.py::test_three")
    scheduler.mark_test_failed("test_example.py::test_three")
    scheduler.mark_test_failed("test_example.py::test_three")

    # Verify independent tracking
    assert scheduler.test_passes["test_example.py::test_one"] == 2
    assert scheduler.test_failures.get("test_example.py::test_one", 0) == 0

    assert scheduler.test_passes.get("test_example.py::test_two", 0) == 0
    assert scheduler.test_failures["test_example.py::test_two"] == 1

    assert scheduler.test_passes["test_example.py::test_three"] == 1
    assert scheduler.test_failures["test_example.py::test_three"] == 2


def test_last_success_time_updates_on_subsequent_passes(pytester):
    """Test that last success time is updated on each pass."""
    pytester.makepyfile("""
        def test_dummy():
            pass
    """)
    config = pytester.parseconfigure("--tx", "2*popen")

    from pytest_load_testing.scheduler import LoadTestScheduler
    scheduler = LoadTestScheduler(config, None)
    scheduler.collection = ["test_example.py::test_one"]

    # First pass
    scheduler.mark_test_passed("test_example.py::test_one")
    first_timestamp = scheduler.last_success_time["test_example.py::test_one"]

    # Wait a bit
    time.sleep(0.01)

    # Second pass
    scheduler.mark_test_passed("test_example.py::test_one")
    second_timestamp = scheduler.last_success_time["test_example.py::test_one"]

    # Verify timestamp was updated
    assert second_timestamp > first_timestamp


def test_tracking_without_collection_does_nothing(pytester):
    """Test that tracking methods handle missing collection gracefully."""
    pytester.makepyfile("""
        def test_dummy():
            pass
    """)
    config = pytester.parseconfigure("--tx", "2*popen")

    from pytest_load_testing.scheduler import LoadTestScheduler
    scheduler = LoadTestScheduler(config, None)
    scheduler.collection = None

    # These should not raise exceptions
    scheduler.mark_test_failed("test_example.py::test_one")
    scheduler.mark_test_passed("test_example.py::test_one")

    # Verify no tracking occurred
    assert len(scheduler.test_failures) == 0
    assert len(scheduler.test_passes) == 0
    assert len(scheduler.last_success_time) == 0


def test_mixed_pass_fail_sequence(pytester):
    """Test tracking with mixed pass/fail sequences."""
    pytester.makepyfile("""
        def test_dummy():
            pass
    """)
    config = pytester.parseconfigure("--tx", "2*popen")

    from pytest_load_testing.scheduler import LoadTestScheduler
    scheduler = LoadTestScheduler(config, None)
    scheduler.collection = ["test_example.py::test_one"]

    # Simulate a sequence: fail, fail, pass, fail, pass, pass
    scheduler.mark_test_failed("test_example.py::test_one")
    scheduler.mark_test_failed("test_example.py::test_one")
    scheduler.mark_test_passed("test_example.py::test_one")
    scheduler.mark_test_failed("test_example.py::test_one")
    scheduler.mark_test_passed("test_example.py::test_one")
    scheduler.mark_test_passed("test_example.py::test_one")

    # Verify final counts
    assert scheduler.test_failures["test_example.py::test_one"] == 3
    assert scheduler.test_passes["test_example.py::test_one"] == 3
    assert "test_example.py::test_one" in scheduler.last_success_time


def test_failure_tracking_integration(pytester):
    """Integration test: verify failure tracking works during actual test execution."""
    # Create a conftest that will capture the scheduler for inspection
    pytester.makeconftest("""
        import pytest
        from pytest_load_testing.constants import stash_key_scheduler

        pytest_plugins = ['pytest_load_testing.concurrent_fixtures']

        captured_scheduler = None

        @pytest.hookimpl(trylast=True)
        def pytest_sessionfinish(session):
            global captured_scheduler
            captured_scheduler = session.config.stash.get(stash_key_scheduler, None)

            # Write tracking data to a file for verification
            if captured_scheduler:
                import json
                tracking_data = {
                    'test_passes': dict(captured_scheduler.test_passes),
                    'test_failures': dict(captured_scheduler.test_failures),
                    'has_last_success_time': list(captured_scheduler.last_success_time.keys())
                }
                with open('tracking_data.json', 'w') as f:
                    json.dump(tracking_data, f)
    """)

    pytester.makepyfile("""
        import pytest
        from pytest_load_testing import stop_load_testing

        @pytest.fixture(scope="session")
        def run_count(shared_json_fixture_factory):
            return shared_json_fixture_factory(
                "run_count",
                on_first_worker={'failing': 0, 'passing': 0}
            )

        def test_failing(run_count):
            with run_count.locked_dict() as data:
                data['failing'] += 1
                failing_count = data['failing']

            if failing_count < 3:
                assert False, "Intentional failure"
            assert True

        def test_passing(request, run_count):
            with run_count.locked_dict() as data:
                data['passing'] += 1
                failing_count = data['failing']
                passing_count = data['passing']

            # Stop after enough iterations to see tracking
            if failing_count >= 3 and passing_count >= 3:
                stop_load_testing(request, "Test complete")
            assert True
    """)

    result = pytester.runpytest('--load-test', '-n', '2', '-v')

    # Verify tests ran and load testing stopped
    result.stdout.fnmatch_lines([
        '*Interrupted: Test complete*',
    ])
    assert result.ret == pytest.ExitCode.INTERRUPTED

    # Verify tracking data was captured
    import json
    tracking_file = pytester.path / 'tracking_data.json'
    assert tracking_file.exists(), "Tracking data file should exist"

    with open(tracking_file) as f:
        tracking_data = json.load(f)

    # Verify both tests were tracked
    assert len(tracking_data['test_passes']) > 0, "Should have pass tracking"
    assert len(tracking_data['test_failures']) > 0, "Should have failure tracking"

    # Verify test_failing had failures
    failing_test_key = [k for k in tracking_data['test_failures'].keys() if 'test_failing' in k]
    assert len(failing_test_key) == 1, "Should track test_failing"
    assert tracking_data['test_failures'][failing_test_key[0]] >= 2, "test_failing should have at least 2 failures"

    # Verify test_passing had passes
    passing_test_key = [k for k in tracking_data['test_passes'].keys() if 'test_passing' in k]
    assert len(passing_test_key) == 1, "Should track test_passing"
    assert tracking_data['test_passes'][passing_test_key[0]] >= 3, "test_passing should have at least 3 passes"

    # Verify last_success_time was updated for passing test
    assert len(tracking_data['has_last_success_time']) > 0, "Should have last success timestamps"
    assert any('test_passing' in k for k in tracking_data['has_last_success_time']), "test_passing should have last success time"

# Made with Bob
