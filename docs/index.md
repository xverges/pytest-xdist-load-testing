# pytest-xdist-load-testing

A pytest-xdist scheduler for continuous load testing with weighted test selection.

## Overview

`pytest-xdist-load-testing` provides a custom scheduler for pytest-xdist that enables continuous load testing scenarios. Tests are selected randomly based on configurable weights, allowing you to simulate realistic load patterns.

## Key Features

- **Continuous Execution**: Tests run repeatedly until manually interrupted
- **Weighted Selection**: Control test frequency with the `@weight` decorator
- **Skip Detection**: Automatically detects and prevents re-scheduling of skipped tests
- **Graceful Shutdown**: Tests can stop the scheduler programmatically

## Installation

```bash
pip install git+https://github.com/xverges/pytest-xdist-load-testing.git
```

## Quick Start

### Basic Usage

Run tests continuously with 4 workers using the `--load-test` flag:

```bash
pytest --load-test -n 4 path/to/test_module.py
```

**Important**: Load testing requires specifying a single test module. Running multiple modules will result in an error.

### Weighted Tests

```python
from pytest_load_testing import weight

@weight(60)  # 60% of requests
def test_read_operations():
    response = api.get("/data")
    assert response.status_code == 200

@weight(30)  # 30% of requests
def test_write_operations():
    response = api.post("/data", json={"key": "value"})
    assert response.status_code == 201

@weight(10)  # 10% of requests
def test_delete_operations():
    response = api.delete("/data/123")
    assert response.status_code == 204
```

### Stopping the Scheduler

```python
from pytest_load_testing import stop_load_testing

def test_with_condition(request):
    if critical_error_detected():
        stop_load_testing(request, "Critical error")
```

## How It Works

1. Enable with `--load-test` flag and pytest-xdist (`-n` option)
2. The plugin implements `pytest_xdist_make_scheduler` hook
3. Returns a `LoadTestScheduler` that continuously supplies tests to workers
4. Tests are selected using `random.choices` with weights as probabilities
5. Tests without `@weight` decorator default to weight=1
6. Scheduler runs until interrupted (Ctrl+C) or stopped programmatically
7. Only works with a single test module to ensure proper fixture handling

## API Reference

### Decorators

#### `@weight(value: int)`

Set the weight for a test. Higher weights mean higher selection probability.

```python
@weight(5)
def test_example():
    pass
```

### Functions

#### `stop_load_testing(request, message)`

Function to stop the scheduler gracefully.

**Parameters:**

- `request`: The pytest request fixture (required)
- `message`: The reason for stopping (optional, default: "Test requested stop")

```python
from pytest_load_testing import stop_load_testing

def test_example(request):
    if condition:
        stop_load_testing(request, "Reason for stopping")
```

## Concurrent Fixtures

When running load tests with multiple workers (`-n` option), you may need to share state across workers. The plugin provides utilities for thread-safe shared state using file-based JSON storage.

### SharedJson

The [`SharedJson`](../src/pytest_load_testing/concurrent_fixtures.py:19) class provides atomic operations on a JSON file, ensuring data consistency when multiple workers access the same data concurrently.

**Key Features:**

- Thread-safe read/write operations with FileLock
- Atomic read-modify-write with context manager
- All data must be JSON-serializable (dict, list, str, int, float, bool, None)

**Methods:**

#### `locked_dict()`

Context manager for atomic read-modify-write operations:

```python
with shared.locked_dict() as data:
    data['count'] = data.get('count', 0) + 1
    data.setdefault('errors', []).append(error)
```

#### `read()`

Read current data atomically (read-only snapshot):

```python
data = shared.read()
count = data.get('count', 0)
```

#### `update(updates)`

Update specific keys atomically:

```python
shared.update({'count': 5, 'status': 'active'})
```

### shared_json_fixture_factory

The [`shared_json_fixture_factory`](../src/pytest_load_testing/concurrent_fixtures.py:121) is a session-scoped fixture that creates SharedJson instances with proper worker coordination.

**Parameters:**

- `name`: Unique name for this fixture (used in file paths)
- `on_first_worker`: Initial data (dict) or callback (callable) for first worker
- `on_last_worker`: Optional callback called by last worker during teardown
- `timeout`: Timeout in seconds for lock acquisition (-1 = wait forever)

**Example - API Rate Tracker:**

```python
import pytest
import time

@pytest.fixture(scope="session")
def api_rate_tracker(shared_json_fixture_factory):
    """Track API call rate limits across all workers."""
    
    def init():
        """Initialize rate limiter on first worker."""
        return {
            'count': 0,
            'limit': 100,
            'errors': [],
            'start_time': time.time()
        }
    
    def report(shared):
        """Report final statistics on last worker."""
        data = shared.read()
        duration = time.time() - data.get('start_time', time.time())
        print(f"Total API calls: {data.get('count', 0)}")
        print(f"Rate: {data.get('count', 0)/duration:.2f} calls/sec")
    
    return shared_json_fixture_factory(
        name="api_rate_tracker",
        on_first_worker=init,
        on_last_worker=report
    )

def test_api_call(api_rate_tracker):
    """Test with rate tracking."""
    with api_rate_tracker.locked_dict() as data:
        data['count'] = data.get('count', 0) + 1
        
        # Check rate limit
        if data['count'] > data.get('limit', 100):
            data.setdefault('errors', []).append({
                "test": "test_api_call",
                "time": time.time(),
                "count": data['count']
            })
```

**Example - Error Collector:**

```python
@pytest.fixture(scope="session")
def error_collector(shared_json_fixture_factory):
    """Collect errors from all workers."""
    
    initial_data = {
        'errors': [],
        'total_tests': 0
    }
    
    def report(shared):
        """Print error summary."""
        data = shared.read()
        print(f"Total tests: {data.get('total_tests', 0)}")
        print(f"Total errors: {len(data.get('errors', []))}")
    
    return shared_json_fixture_factory(
        name="error_collector",
        on_first_worker=initial_data,
        on_last_worker=report
    )

def test_with_error_tracking(error_collector):
    """Test with error collection."""
    with error_collector.locked_dict() as data:
        data['total_tests'] = data.get('total_tests', 0) + 1
        # Collect errors as needed
        data.setdefault('errors', []).append("Some error")
```

**Worker Coordination:**

The factory handles worker coordination automatically:

1. **First Worker**: Executes `on_first_worker` callback to initialize data
2. **All Workers**: Access shared data through the returned SharedJson instance
3. **Last Worker**: Executes `on_last_worker` callback during teardown
4. **Cleanup**: Last worker removes all temporary files

## Rate Limiting

The plugin provides a [`rate_limiter_fixture_factory`](../src/pytest_load_testing/concurrent_fixtures.py:305) for enforcing rate limits across pytest-xdist workers. This is essential for load testing scenarios where you need to respect API rate limits or simulate realistic traffic patterns.

### Overview

The rate limiter uses the **token bucket algorithm**, which allows controlled bursts of activity while maintaining an average rate over time. State is synchronized across all workers using file-based locking.

### Basic Usage

```python
import pytest
from pytest_load_testing import weight
from pytest_load_testing.token_bucket_rate_limiter import RateLimit

@pytest.fixture(scope="session")
def api_limiter(rate_limiter_fixture_factory):
    """Rate limiter for API calls."""
    return rate_limiter_fixture_factory(
        name="api_limiter",
        hourly_rate=RateLimit.per_second(10)  # 10 calls per second
    )

@weight(1)
def test_api_call(api_limiter):
    with api_limiter.rate_limited_context() as ctx:
        # Context entry waits if rate limit would be exceeded
        response = api.get("/data")
        assert response.status_code == 200
        assert ctx.call_count >= 1
```

### Rate Limit Helpers

The `RateLimit` class provides convenient factory methods:

```python
RateLimit.per_second(10)   # 10 calls per second (36,000/hour)
RateLimit.per_minute(600)  # 600 calls per minute (36,000/hour)
RateLimit.per_hour(3600)   # 3600 calls per hour
RateLimit.per_day(86400)   # 86400 calls per day (3,600/hour)
```

### Factory Parameters

```python
rate_limiter_fixture_factory(
    name: str,                                    # Unique identifier
    hourly_rate: Union[RateLimit, Callable],      # Rate limit specification
    max_drift: float = 0.1,                       # Max deviation (0-1)
    on_drift_callback: Optional[Callable] = None, # Drift detection callback
    num_calls_between_checks: int = 10,           # Calls between rate checks
    seconds_before_first_check: float = 60.0,     # Delay before first check
    burst_capacity: Optional[int] = None,         # Max burst size
    max_calls: int = -1,                          # Total call limit
    max_call_callback: Optional[Callable] = None  # Max calls callback
)
```

### Advanced Examples

#### Rate Limiting with Drift Detection

Stop tests if actual rate exceeds target by more than 20%:

```python
import pytest
from pytest_load_testing import weight, stop_load_testing
from pytest_load_testing.token_bucket_rate_limiter import RateLimit

@pytest.fixture(scope="session")
def monitored_api(rate_limiter_fixture_factory, request):
    """API limiter with drift detection."""
    
    def on_drift(limiter_id, current_rate, target_rate, drift):
        """Stop testing when drift exceeds threshold."""
        message = (
            f"Rate drift for {limiter_id} exceeds maximum: "
            f"current={current_rate:.2f}/hr, target={target_rate}/hr, "
            f"drift={drift:.2%}"
        )
        stop_load_testing(request, message)
    
    return rate_limiter_fixture_factory(
        name="monitored_api",
        hourly_rate=RateLimit.per_second(100),
        max_drift=0.2,  # 20% tolerance
        num_calls_between_checks=50,
        seconds_before_first_check=5.0,
        on_drift_callback=on_drift
    )

@weight(1)
def test_api_with_monitoring(monitored_api):
    with monitored_api.rate_limited_context() as ctx:
        response = api.get("/data")
        assert response.status_code == 200
```

#### Rate Limiting with Max Calls

Limit total number of calls and stop when reached:

```python
@pytest.fixture(scope="session")
def limited_api(rate_limiter_fixture_factory, request):
    """API limiter with max calls."""
    
    def on_max_calls(limiter_id, count):
        """Stop when max calls reached."""
        stop_load_testing(request, f"Max calls reached: {count}")
    
    return rate_limiter_fixture_factory(
        name="limited_api",
        hourly_rate=RateLimit.per_minute(600),
        max_calls=1000,
        max_call_callback=on_max_calls
    )

@weight(1)
def test_limited_api(limited_api):
    with limited_api.rate_limited_context():
        response = api.post("/data", json={"key": "value"})
        assert response.status_code == 201
```

#### Dynamic Rate Limiting

Adjust rate limits dynamically during test execution:

```python
@pytest.fixture(scope="session")
def adaptive_limiter(rate_limiter_fixture_factory):
    """Rate limiter with dynamic rate adjustment."""
    current_rate = [RateLimit.per_second(10)]
    
    def get_rate():
        return current_rate[0]
    
    limiter = rate_limiter_fixture_factory(
        name="adaptive",
        hourly_rate=get_rate
    )
    limiter.rate_control = current_rate
    return limiter

@weight(1)
def test_with_rate_change(adaptive_limiter):
    # Increase rate for this test
    adaptive_limiter.rate_control[0] = RateLimit.per_second(20)
    
    with adaptive_limiter.rate_limited_context():
        response = api.get("/data")
        assert response.status_code == 200
```

#### Burst Capacity Control

Allow bursts above average rate:

```python
@pytest.fixture(scope="session")
def bursty_api(rate_limiter_fixture_factory):
    """API limiter allowing bursts."""
    return rate_limiter_fixture_factory(
        name="bursty_api",
        hourly_rate=RateLimit.per_second(10),
        burst_capacity=50  # Allow bursts up to 50 calls
    )

@weight(1)
def test_burst_handling(bursty_api):
    # Can make rapid calls up to burst capacity
    with bursty_api.rate_limited_context():
        response = api.get("/data")
        assert response.status_code == 200
```

### Context Manager Details

The `rate_limited_context()` context manager:

- **Waits** if necessary to respect the rate limit before entering
- **Tracks** call count, exceptions, and timing
- **Yields** a progress object with attributes:
  - `id`: The limiter name
  - `call_count`: Total calls made
  - `exceptions`: Total exceptions encountered
  - `start_time`: When rate limiting started (timestamp)
  - `hourly_rate`: Current rate limit in calls per hour

```python
with api_limiter.rate_limited_context() as ctx:
    print(f"Limiter: {ctx.id}")
    print(f"Call count: {ctx.call_count}")
    print(f"Rate: {ctx.hourly_rate} calls/hour")
    # Make your API call here
```

### Thread Safety

All rate limiter state is synchronized across workers using file-based locking via `SharedJson`. Multiple workers can safely share the same rate limiter instance without race conditions.

## License

MIT License - see LICENSE file for details.
