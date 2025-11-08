=========================
pytest-xdist-load-testing
=========================

.. .. image:: https://img.shields.io/pypi/v/pytest-xdist-load-testing.svg
..     :target: https://pypi.org/project/pytest-xdist-load-testing
..     :alt: PyPI version
..
.. .. image:: https://img.shields.io/pypi/pyversions/pytest-xdist-load-testing.svg
..     :target: https://pypi.org/project/pytest-xdist-load-testing
..     :alt: Python versions

.. image:: https://github.com/xverges/pytest-xdist-load-testing/actions/workflows/main.yml/badge.svg
    :target: https://github.com/xverges/pytest-xdist-load-testing/actions/workflows/main.yml
    :alt: See Build Status on GitHub Actions

A pytest-xdist scheduler for continuous load testing with weighted test selection

----

This `pytest`_ plugin was generated with `Cookiecutter`_ along with `@hackebrot`_'s `cookiecutter-pytest-plugin`_ template.


Features
--------

* **Continuous Test Execution**: Runs tests repeatedly until manually interrupted
* **Weighted Test Selection**: Control test execution frequency using the ``@weight`` decorator
* **Random Selection**: Tests are selected randomly based on their weights using ``random.choices``
* **Graceful Interruption**: Tests and fixtures can stop the scheduler programmatically
* **pytest-xdist Integration**: Seamlessly integrates with pytest-xdist's distributed testing


Requirements
------------

* Python 3.8+
* pytest >= 6.2.0
* pytest-xdist >= 2.0.0


Installation
------------

Install directly from the GitHub repository::

    $ pip install git+https://github.com/xverges/pytest-xdist-load-testing.git


Usage
-----

Basic Load Testing
~~~~~~~~~~~~~~~~~~

Run your tests with pytest-xdist to enable the load testing scheduler::

    $ pytest --load-test -n 4 path/to/test_module.py  # Run with 4 workers

The scheduler will continuously supply tests to workers until interrupted (Ctrl+C).

**Important**: Load testing requires specifying a single test module. Running multiple modules will result in an error::

    $ pytest --load-test -n 4 tests/  # ERROR: Multiple modules detected
    $ pytest --load-test -n 4 test_a.py test_b.py  # ERROR: Multiple modules

This restriction ensures proper fixture handling and test isolation during continuous execution.


Weighted Tests
~~~~~~~~~~~~~~

Use the ``@weight`` decorator to control how frequently tests are selected:

.. code-block:: python

    from pytest_load_testing import weight

    @weight(1)
    def test_rare_operation():
        """This test runs less frequently"""
        assert perform_rare_check()

    @weight(10)
    def test_common_operation():
        """This test runs 10x more frequently"""
        assert perform_common_check()

    def test_default_weight():
        """Tests without @weight have weight=1"""
        assert True

Tests with higher weights are more likely to be selected. The probability is proportional to the weight.


Stopping the Scheduler
~~~~~~~~~~~~~~~~~~~~~~

Tests can stop the scheduler programmatically using the ``stop_load_testing`` function:

.. code-block:: python

    from pytest_load_testing import stop_load_testing

    def test_with_stop_condition(request):
        result = check_system_health()
        if result.critical_failure:
            stop_load_testing(request, "Critical failure detected")


Command Line Options
~~~~~~~~~~~~~~~~~~~~

The plugin adds the following command line option::

    --load-test    Enable load testing mode with continuous test execution


Examples
~~~~~~~~

**Load test with weighted distribution:**

.. code-block:: python

    from pytest_load_testing import weight

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

**Conditional stop with shared state across workers:**

.. code-block:: python

    import pytest
    from pytest_load_testing import weight, stop_load_testing

    @pytest.fixture(scope="session")
    def error_tracker(shared_json_fixture_factory):
        """Track errors across all workers."""
        return shared_json_fixture_factory(
            name="errors",
            on_first_worker={'count': 0}
        )

    @weight(1)
    def test_health_check(request, error_tracker):
        response = api.get("/health")
        if response.json()["status"] == "critical":
            stop_load_testing(request, "System health critical")
        assert response.status_code == 200

    @weight(10)
    def test_normal_operation(error_tracker):
        try:
            assert api.get("/api/data").status_code == 200
        except AssertionError:
            with error_tracker.locked_dict() as data:
                data['count'] += 1

See the full documentation for more details on concurrent fixtures and shared state.


Rate Limiting
~~~~~~~~~~~~~

The plugin provides a ``rate_limiter_fixture_factory`` for enforcing rate limits across workers:

.. code-block:: python

    import pytest
    from pytest_load_testing import weight, stop_load_testing
    from pytest_load_testing.token_bucket_rate_limiter import RateLimit

    @pytest.fixture(scope="session")
    def api_limiter(rate_limiter_fixture_factory, request):
        """Rate limiter that stops tests if rate drift exceeds 20%."""

        def on_drift(limiter_id, current_rate, target_rate, drift):
            message = (
                f"Rate drift for {limiter_id}: "
                f"current={current_rate:.2f}/hr, target={target_rate}/hr, "
                f"drift={drift:.2%}"
            )
            stop_load_testing(request, message)

        return rate_limiter_fixture_factory(
            name="api_limiter",
            hourly_rate=RateLimit.per_second(10),  # 10 calls/second
            max_drift=0.2,  # 20% tolerance
            on_drift_callback=on_drift
        )

    @weight(1)
    def test_api_call(api_limiter):
        with api_limiter.rate_limited_context() as ctx:
            # Context entry waits if rate limit would be exceeded
            response = api.get("/data")
            assert response.status_code == 200
            assert ctx.call_count >= 1

**Key Features:**

* **Token Bucket Algorithm**: Allows controlled bursts while maintaining average rate
* **Shared State**: Rate limiting coordinated across all workers
* **Drift Detection**: Monitors actual vs. target rate and triggers callbacks
* **Max Calls**: Optional limit on total calls with callback
* **Dynamic Rates**: Support for callable rate functions

**Rate Limit Helpers:**

.. code-block:: python

    RateLimit.per_second(10)   # 10 calls per second
    RateLimit.per_minute(600)  # 600 calls per minute
    RateLimit.per_hour(3600)   # 3600 calls per hour
    RateLimit.per_day(86400)   # 86400 calls per day

See the full documentation for more examples and advanced usage.


License
-------

Distributed under the terms of the `MIT`_ license, "pytest-xdist-load-testing" is free and open source software


Issues
------

If you encounter any problems, please `file an issue`_ along with a detailed description.

.. _`Cookiecutter`: https://github.com/audreyr/cookiecutter
.. _`@hackebrot`: https://github.com/hackebrot
.. _`MIT`: https://opensource.org/licenses/MIT
.. _`cookiecutter-pytest-plugin`: https://github.com/pytest-dev/cookiecutter-pytest-plugin
.. _`file an issue`: https://github.com/xverges/pytest-xdist-load-testing/issues
.. _`pytest`: https://github.com/pytest-dev/pytest
.. _`tox`: https://tox.readthedocs.io/en/latest/
.. _`pip`: https://pypi.org/project/pip/
.. _`PyPI`: https://pypi.org/project
