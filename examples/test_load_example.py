"""
Example: Load testing with weighted distribution and shared state

Run with: pytest -n auto --load-test examples/test_load_example.py

This demonstrates:
1. Weighted test selection (tests run with different frequencies)
2. Shared state tracking across workers using shared_json_fixture_factory
3. Conditional stopping based on shared state

TEST_CODE:
```python
result = pytester.runpytest('--load-test', '-n', '2', '-v')
result.stdout.fnmatch_lines([
    '*Interrupted: System health critical*',
])
assert result.ret == pytest.ExitCode.INTERRUPTED
```
"""

import logging
import sys

import pytest

from pytest_load_testing import stop_load_testing, weight

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def progress_tracker(request, shared_json_fixture_factory):
    """Track errors across all workers."""

    def on_last_worker(shared):
        """Called once by the last worker to finish."""
        # Read the data that was collected during test execution
        data = shared.read()

        # Write to a file to prove callback executed
        with open("/tmp/load_test_report.txt", "w") as f:
            f.write("=" * 60 + "\n")
            f.write("LOAD TEST REPORT\n")
            f.write("=" * 60 + "\n")
            f.write(f"Total test executions: {data.get('count', 0)}\n")
            f.write("=" * 60 + "\n")

        # Also write to stderr
        report = []
        report.append("\n" + "=" * 60)
        report.append("LOAD TEST REPORT")
        report.append("=" * 60)
        report.append(f"\nTotal test executions: {data.get('count', 0)}")
        report.append("=" * 60 + "\n")
        sys.stderr.write("\n".join(report))
        sys.stderr.flush()

    return shared_json_fixture_factory(name="counter", on_first_worker={"count": 0}, on_last_worker=on_last_worker)


@pytest.fixture
def iteration_counter(request, progress_tracker):
    """Common fixture that tracks iterations and stops after threshold."""
    with progress_tracker.locked_dict() as data:
        data["count"] = data.get("count", 0) + 1
        current_count = data["count"]

    # Stop after 20 total test executions across all workers
    if current_count >= 100:
        stop_load_testing(request, "System health critical")


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
