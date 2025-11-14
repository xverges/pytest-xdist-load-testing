"""
Example: Load testing with weighted distribution

Run with: pytest -n auto --load-test examples/test_load_example.py

This demonstrates:
1. Weighted test selection (tests run with different frequencies)
2. Conditional stopping based on iteration count

TEST_CODE:
```python
result = run_with_timeout(pytester, '--load-test', '-n', '2', '-v')
# Should complete successfully with interrupt
assert result.ret == pytest.ExitCode.INTERRUPTED
result.stdout.fnmatch_lines([
    '*Interrupted: Test session completed*',
])
```
"""

import pytest

from pytest_xdist_load_testing import stop_load_testing, weight

# Simple counter - note this won't work across xdist workers
# but is sufficient for demonstration purposes
_iteration_count = 0


@pytest.fixture
def iteration_counter(request):
    """Common fixture that tracks iterations and stops after threshold."""
    global _iteration_count
    _iteration_count += 1

    # Stop after 50 total test executions (reduced for faster testing)
    if _iteration_count >= 50:
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
