"""Test that weight decorator actually affects test distribution."""
import pytest
import tempfile
import os
import fcntl
from pytest_load_testing import weight, stop_load_testing


COUNTER_FILE = os.path.join(tempfile.gettempdir(), 'pytest_weight_test_counter.txt')

def get_count(test_name):
    """Read count for a specific test from the counter file."""
    if not os.path.exists(COUNTER_FILE):
        return 0

    with open(COUNTER_FILE, 'r') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        try:
            for line in f:
                if line.strip():
                    name, count = line.strip().split(':')
                    if name == test_name:
                        return int(count)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    return 0

def test_weight_distribution_verification(pytester):
    """
    Test that weights actually affect test distribution.

    This test creates two tests with very different weights (1 vs 100)
    and runs them multiple times. The high-weight test should be selected
    significantly more often than the low-weight test.
    """
    pytester.makepyfile(f"""
        import os
        import fcntl
        from pytest_load_testing import weight, stop_load_testing

        COUNTER_FILE = '{COUNTER_FILE}'

        def increment_count(test_name):
            if not os.path.exists(COUNTER_FILE):
                with open(COUNTER_FILE, 'w') as f:
                    pass

            with open(COUNTER_FILE, 'r+') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    counts = {{}}
                    for line in f:
                        if line.strip():
                            name, count = line.strip().split(':')
                            counts[name] = int(count)

                    counts[test_name] = counts.get(test_name, 0) + 1

                    f.seek(0)
                    f.truncate()
                    for name, count in counts.items():
                        f.write(f"{{name}}:{{count}}\\n")

                    return counts[test_name]
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        @weight(1)
        def test_low_weight():
            '''Test with weight 1 - should run rarely.'''
            increment_count('low')
            assert True

        @weight(1)
        def test_stopper(request):
            '''Stop after enough iterations.'''
            low_count = increment_count('low')
            high_count = increment_count('high')
            total = low_count + high_count

            # Stop after 200 total test executions for better statistical sample
            if total >= 200:
                stop_load_testing(request, f"Completed {{total}} iterations")

            assert True

        @weight(100)
        def test_high_weight():
            '''Test with weight 100 - should run frequently.'''
            increment_count('high')
            assert True

    """)

    # Clean up counter file before test
    if os.path.exists(COUNTER_FILE):
        os.remove(COUNTER_FILE)

    # Run the load test
    result = pytester.runpytest('--load-test', '-n', '2', '-v')

    # Should stop gracefully
    assert result.ret == 2

    # Read final counts
    low_count = get_count('low')
    high_count = get_count('high')

    print(f"\nTest execution counts:")
    print(f"  Low weight (1):   {low_count}")
    print(f"  High weight (100): {high_count}")

    # With proper weighting, high_count should be much larger than low_count
    # Expected ratio is approximately 100:1, but we'll be conservative
    # and just check that high_count is at least 10x low_count
    assert high_count > 0, "High weight test should have run at least once"
    assert low_count > 0, "Low weight test should have run at least once"

    ratio = high_count / low_count if low_count > 0 else float('inf')
    print(f"  Ratio (high/low): {ratio:.2f}")

    # If weights are working, ratio should be much higher than 10
    # If weights are NOT working (all weights=1), ratio will be close to 1
    assert ratio > 10, (
        f"Weight distribution is broken! "
        f"Expected high_count >> low_count, but got ratio of {ratio:.2f}. "
        f"This suggests all tests have equal weight (weight decorator not working)."
    )

    # Clean up
    if os.path.exists(COUNTER_FILE):
        os.remove(COUNTER_FILE)
