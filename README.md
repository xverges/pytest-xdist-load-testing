# pytest-xdist-load-testing

[![PyPI version](https://img.shields.io/pypi/v/pytest-xdist-load-testing.svg)](https://pypi.org/project/pytest-xdist-load-testing)
[![Python versions](https://img.shields.io/pypi/pyversions/pytest-xdist-load-testing.svg)](https://pypi.org/project/pytest-xdist-load-testing)
[![Build Status](https://github.com/xverges/pytest-xdist-load-testing/actions/workflows/main.yml/badge.svg)](https://github.com/xverges/pytest-xdist-load-testing/actions/workflows/main.yml)

A pytest-xdist scheduler for continuous load testing with weighted test selection

## Features

* **Continuous Test Execution**: Runs tests repeatedly until manually interrupted
* **Weighted Test Selection**: Control test execution frequency using the `@weight` decorator
* **Random Selection**: Tests are selected randomly based on their weights using `random.choices`
* **Graceful Interruption**: Tests and fixtures can stop the scheduler programmatically
* **pytest-xdist Integration**: Seamlessly integrates with pytest-xdist's distributed testing

## Requirements

* Python 3.9+
* pytest >= 8.4.2
* pytest-xdist >= 3.8.0

## Installation

```bash
pip install git+https://github.com/xverges/pytest-xdist-load-testing.git
```

## Examples

See the [`examples/`](https://github.com/xverges/pytest-xdist-load-testing/tree/main/examples)
folder for working examples.

### Basic Load Testing

Run your tests with pytest-xdist to enable the load testing scheduler:

```bash
pytest --load-test -n 4 path/to/test_module.py  # Run with 4 workers
```

The scheduler will continuously supply tests to workers until interrupted (Ctrl+C).

**Important**: Load testing requires specifying a single test module. Running multiple modules will result in an error:

```bash
pytest --load-test -n 4 tests/  # ERROR: Multiple modules detected
pytest --load-test -n 4 test_a.py test_b.py  # ERROR: Multiple modules
```

This restriction ensures proper fixture handling and test isolation during continuous execution.

### Stopping the Scheduler

Tests can stop the scheduler programmatically using the `stop_load_testing` function:

```python
from pytest_xdist_load_testing import stop_load_testing

def test_with_stop_condition():
    result = check_system_health()
    if result.critical_failure:
        stop_load_testing("Critical failure detected")
```

### Load Test with Weighted Distribution

```python
from pytest_xdist_load_testing import weight

@weight(70)
def test_read_heavy():
    """70% of requests"""
    assert api.get("/data").status_code == 200

@weight(20)
def test_write_operations():
    """20% of requests"""
    assert api.post("/data", json={}).status_code == 201

@weight(10)
def test_admin_operations():
    """10% of requests"""
    assert api.delete("/data/old").status_code == 204
```

## Command Line Options

The plugin adds the following command line option:

```text
--load-test    Enable load testing mode with continuous test execution
```

## Rate Limiting and Shared State

For rate limiting and shared state management across pytest-xdist workers,
see the companion package [pytest-xdist-rate-limit](https://github.com/xverges/pytest-xdist-rate-limit).

## Documentation

📚 **[Full Documentation](https://xverges.github.io/pytest-xdist-load-testing/)**

* [API Reference](https://xverges.github.io/pytest-xdist-load-testing/api/reference/) - Complete API documentation

## License

Distributed under the terms of the [MIT](https://opensource.org/licenses/MIT) license, "pytest-xdist-load-testing" is free and open source software

## Issues

If you encounter any problems, please [file an issue](https://github.com/xverges/pytest-xdist-load-testing/issues) along with a detailed description.

---

This [pytest](https://github.com/pytest-dev/pytest) plugin was generated with [Cookiecutter](https://github.com/audreyr/cookiecutter) along with [@hackebrot](https://github.com/hackebrot)'s [cookiecutter-pytest-plugin](https://github.com/pytest-dev/cookiecutter-pytest-plugin) template.
