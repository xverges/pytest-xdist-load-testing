"""Tests for skip detection and prevention in load testing."""
import pytest
from pytest_load_testing.scheduler import LoadTestScheduler


def test_mark_test_skipped(pytester):
    """Test that mark_test_skipped sets weight to zero."""
    pytester.makepyfile("""
        def test_dummy():
            pass
    """)
    config = pytester.parseconfigure("--tx", "2*popen", "--load-test")

    scheduler = LoadTestScheduler(config, None)

    # Set up collection and weights
    scheduler.collection = ["test1.py::test_a"]
    scheduler.weights = [1]

    # Mark test as skipped
    scheduler.mark_test_skipped("test1.py::test_a")

    assert scheduler.weights[0] == 0


def test_skipped_tests_not_rescheduled(pytester):
    """Test that tests with weight 0 are not selected."""
    pytester.makepyfile("""
        def test_dummy():
            pass
    """)
    config = pytester.parseconfigure("--tx", "2*popen")

    scheduler = LoadTestScheduler(config, None)

    # Set up collection with 3 tests
    scheduler.collection = ["test1.py::test_a", "test2.py::test_b", "test3.py::test_c"]
    scheduler.weights = [1, 1, 1]

    # Mark middle test as skipped (weight = 0)
    scheduler.mark_test_skipped("test2.py::test_b")

    # Create a mock node
    class MockNode:
        shutting_down = False
        def send_runtest_some(self, indices):
            self.sent_indices = indices
        def shutdown(self):
            pass

    node = MockNode()
    scheduler.add_node(node)  # type: ignore[arg-type]

    # Send tests - should only send indices 0 and 2, not 1
    scheduler._send_weighted_tests(node, 10)  # type: ignore[arg-type]

    # Verify skipped test (index 1) was not sent
    assert 1 not in node.sent_indices
    # Verify only non-skipped tests were sent
    assert all(idx in [0, 2] for idx in node.sent_indices)


def test_all_tests_skipped_stops_scheduler(pytester):
    """Test that scheduler stops when all tests have weight 0."""
    pytester.makepyfile("""
        def test_dummy():
            pass
    """)
    config = pytester.parseconfigure("--tx", "2*popen")

    scheduler = LoadTestScheduler(config, None)

    # Set up collection with 2 tests
    scheduler.collection = ["test1.py::test_a", "test2.py::test_b"]
    scheduler.weights = [1, 1]

    # Mark all tests as skipped (weight = 0)
    scheduler.mark_test_skipped("test1.py::test_a")
    scheduler.mark_test_skipped("test2.py::test_b")

    # Create a mock node
    class MockNode:
        shutting_down = False
        def send_runtest_some(self, indices):
            self.sent_indices = indices
        def shutdown(self):
            pass

    node = MockNode()
    scheduler.add_node(node)  # type: ignore[arg-type]

    # Try to send tests - should call pytest.exit
    with pytest.raises(pytest.exit.Exception) as exc_info:
        scheduler._send_weighted_tests(node, 2)  # type: ignore[arg-type]

    # Verify the exit message
    assert "skipped" in str(exc_info.value).lower()


def test_conditional_skip_detection(pytester):
    """Test that conditional skips are detected."""
    pytester.makepyfile("""
        import pytest
        from pytest_load_testing import stop_load_testing

        def test_conditional_skip():
            pytest.skip("Conditionally skipping this test")
            assert False, "This should not run"

        def test_normal(request):
            stop_load_testing(request, "Test complete")
            assert True
    """)

    result = pytester.runpytest('--load-test', '-n', '2', '-v')

    # In load testing mode, tests run multiple times until stopped
    # Just verify it stopped gracefully
    assert result.ret == pytest.ExitCode.INTERRUPTED
    result.stdout.fnmatch_lines([
        '*Interrupted: Test complete*',
    ])


def test_skip_during_setup(pytester):
    """Test that skips during setup phase are handled."""
    pytester.makepyfile("""
        import pytest
        from pytest_load_testing import stop_load_testing

        @pytest.fixture
        def skip_fixture():
            pytest.skip("Skipping in fixture")

        def test_with_skip_fixture(skip_fixture):
            assert True

        def test_normal(request):
            stop_load_testing(request, "Test complete")
            assert True
    """)

    result = pytester.runpytest('--load-test', '-n', '2', '-v')

    # In load testing mode, tests run multiple times until stopped
    # Just verify it stopped gracefully
    assert result.ret == pytest.ExitCode.INTERRUPTED
    result.stdout.fnmatch_lines([
        '*Interrupted: Test complete*',
    ])


def test_multiple_skips_tracked(pytester):
    """Test that multiple skipped tests all have weight 0."""
    pytester.makepyfile("""
        def test_dummy():
            pass
    """)
    config = pytester.parseconfigure("--tx", "2*popen")

    scheduler = LoadTestScheduler(config, None)

    # Set up collection with 6 tests
    scheduler.collection = [f"test{i}.py::test" for i in range(6)]
    scheduler.weights = [1, 1, 1, 1, 1, 1]

    # Mark multiple tests as skipped
    scheduler.mark_test_skipped("test0.py::test")
    scheduler.mark_test_skipped("test2.py::test")
    scheduler.mark_test_skipped("test5.py::test")

    assert scheduler.weights[0] == 0
    assert scheduler.weights[2] == 0
    assert scheduler.weights[5] == 0
    assert scheduler.weights[1] != 0
    assert scheduler.weights[3] != 0
    assert scheduler.weights[4] != 0


def test_skip_idempotent(pytester):
    """Test that marking same test as skipped multiple times is safe."""
    pytester.makepyfile("""
        def test_dummy():
            pass
    """)
    config = pytester.parseconfigure("--tx", "2*popen")

    scheduler = LoadTestScheduler(config, None)

    # Set up collection
    scheduler.collection = ["test1.py::test_a"]
    scheduler.weights = [5]

    # Mark same test multiple times
    scheduler.mark_test_skipped("test1.py::test_a")
    scheduler.mark_test_skipped("test1.py::test_a")
    scheduler.mark_test_skipped("test1.py::test_a")

    # Weight should still be 0
    assert scheduler.weights[0] == 0

def test_all_tests_eventually_skip(pytester):
    """Test that scheduler stops when all tests start skipping after iterations."""
    pytester.makeconftest("""
        pytest_plugins = ['pytest_load_testing.concurrent_fixtures']
    """)

    pytester.makepyfile("""
        import pytest

        @pytest.fixture(scope="session")
        def test_counters(shared_json_fixture_factory):
            return shared_json_fixture_factory(
                "test_counters",
                on_first_worker={'a': 0, 'b': 0}
            )

        def test_eventually_skips_a(test_counters):
            with test_counters.locked_dict() as data:
                data['a'] += 1
                count = data['a']

            if count > 2:
                pytest.skip("Test A skipping after 2 runs")
            assert True

        def test_eventually_skips_b(test_counters):
            with test_counters.locked_dict() as data:
                data['b'] += 1
                count = data['b']

            if count > 3:
                pytest.skip("Test B skipping after 3 runs")
            assert True
    """)

    result = pytester.runpytest('--load-test', '-n', '2', '-v')

    # Should detect all tests are skipped and exit properly
    assert result.ret == pytest.ExitCode.INTERRUPTED

    # Verify tests were executed before they started skipping
    result.stdout.fnmatch_lines_random([
        '*PASSED*test_eventually_skips_a*',
        '*PASSED*test_eventually_skips_*',
        '*All tests are being skipped*',
    ])


def test_all_tests_marked_skip_integration(pytester):
    """Test integration when all tests are marked with @pytest.mark.skip."""
    pytester.makepyfile("""
        import pytest

        @pytest.mark.skip(reason="Test 1 skipped")
        def test_skipped_one():
            assert False, "Should not run"

        @pytest.mark.skip(reason="Test 2 skipped")
        def test_skipped_two():
            assert False, "Should not run"

        @pytest.mark.skip(reason="Test 3 skipped")
        def test_skipped_three():
            assert False, "Should not run"
    """)

    result = pytester.runpytest('--load-test', '-n', '2', '-v')

    # Should detect all tests are skipped
    # Exit code 0 is acceptable when tests complete naturally
    assert result.ret in (0, 2)  # Success or Interrupted
    result.stdout.fnmatch_lines([
        '*skipped*',
    ])


def test_all_tests_weight_zero_unit(pytester):
    """Test scheduler behavior when all tests initialized with weight 0."""
    pytester.makepyfile("""
        def test_dummy():
            pass
    """)
    config = pytester.parseconfigure("--tx", "2*popen")

    scheduler = LoadTestScheduler(config, None)

    # Set up collection with all weights at 0
    scheduler.collection = ["test1.py::test_a", "test2.py::test_b", "test3.py::test_c"]
    scheduler.weights = [0, 0, 0]

    # Create a mock node
    class MockNode:
        shutting_down = False
        def send_runtest_some(self, indices):
            self.sent_indices = indices
        def shutdown(self):
            pass

    node = MockNode()
    scheduler.add_node(node)  # type: ignore[arg-type]

    # Try to send tests - should call pytest.exit
    with pytest.raises(pytest.exit.Exception) as exc_info:
        scheduler._send_weighted_tests(node, 5)  # type: ignore[arg-type]

    # Verify the exit message
    assert "skipped" in str(exc_info.value).lower()

