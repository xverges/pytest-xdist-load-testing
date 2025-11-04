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

## License

MIT License - see LICENSE file for details.
