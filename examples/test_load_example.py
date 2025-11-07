"""
Example: Load testing with weighted distribution and shared state

Run with: pytest -n auto --load-test examples/test_load_example.py

This demonstrates:
1. Weighted test selection (tests run with different frequencies)
2. Shared state tracking across workers using shared_json_fixture_factory
3. Conditional stopping based on shared state
4. Automatic execution report at session end

TEST_CODE:
```python
result = pytester.runpytest('--load-test', '-n', '2', '-v')
result.stdout.fnmatch_lines([
    '*Interrupted: Test session completed*',
])
assert result.ret == pytest.ExitCode.INTERRUPTED
```
"""

import pytest

from pytest_load_testing import stop_load_testing, weight


@pytest.fixture(scope="session")
def progress_tracker(shared_json_fixture_factory):
    """Track errors across all workers."""
    return shared_json_fixture_factory(name="progress", on_first_worker={"count": 0, "results_by_node": {}})


@pytest.fixture
def iteration_counter(request, progress_tracker):
    """Common fixture that tracks iterations and stops after threshold."""
    node_id = request.node.nodeid

    with progress_tracker.locked_dict() as data:
        data["count"] = data.get("count", 0) + 1
        current_count = data["count"]

        # Track results by node id
        results_by_node = data.get("results_by_node", {})
        results_by_node[node_id] = results_by_node.get(node_id, 0) + 1
        data["results_by_node"] = results_by_node

    # Stop after 100 total test executions across all workers
    if current_count >= 100:
        stop_load_testing(request, "Test session completed")


@weight(70)
def test_read_heavy(iteration_counter):
    """70% of requests - simulates read-heavy operations."""
    assert True


@weight(20)
def test_write_operations(iteration_counter):
    """20% of requests - simulates write operations."""
    assert True


@weight(10)
def test_admin_operations(iteration_counter):
    """10% of requests - simulates admin operations."""
    assert True


@weight(1)
def test_health_check(iteration_counter):
    """1% of requests - simulates health check."""
    assert True
