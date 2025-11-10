"""pytest-xdist-load-testing plugin implementation."""

import logging

import pytest

from .constants import (
    LOAD_TEST_STOP_SIGNAL,
    stash_key_has_been_run,
    stash_key_scheduler,
    stash_key_session,
)
from .scheduler import LoadTestScheduler


class LoadTestPlugin:
    """
    Main plugin class for pytest-xdist-load-testing.

    A single instance is registered with pytest's plugin manager.
    """

    PYTEST_OPTION_NAME = "load_test"
    WEIGHT_PROPERTY_KEY = "load_test_weight"

    def __init__(self):
        self.config = None

    @staticmethod
    def is_enabled(config: pytest.Config) -> bool:
        """Check if load testing is enabled via --load-test flag."""
        return config.getoption(LoadTestPlugin.PYTEST_OPTION_NAME, False)

    @pytest.hookimpl(tryfirst=True)
    def pytest_xdist_make_scheduler(self, config, log):
        """
        Main hook: return our LoadTestScheduler
        """
        if not self.is_enabled(config):
            return None

        scheduler = LoadTestScheduler(config, log)
        config.stash[stash_key_scheduler] = scheduler
        return scheduler

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_setup(self, item: pytest.Item):
        """
        Hook called before running test setup phase.

        Load testing strategy for single-module execution:
        - Function fixtures: Always setup/teardown for every test run
        - Module/session fixtures: Setup once, persist across runs, teardown when worker stops
        - No complex teardown suspension needed - module fixtures naturally persist

        This is simpler than pytest-rerunfailures because:
        1. We're not retrying failures - just running tests continuously
        2. All tests are in the same module
        3. Module/session fixtures don't need special handling

        Also extracts weight from @weight marker and adds to user_properties for
        collection during first iteration.
        """
        # Only reinitialize in load testing mode
        if not self.is_enabled(item.config):
            return None

        self._save_weight_for_controller(item)

        # Check if this item has been run before
        # We use stash to track this
        has_been_run = item.stash.get(stash_key_has_been_run, False)
        request_obj = getattr(item, "_request", None)

        # If item has been run before, we need to clear fixtures for re-execution
        if has_been_run and request_obj is not None:  # type: ignore[attr-defined]
            self._cleanup_previous_run(item)

        # Get ready for next time
        item.stash[stash_key_has_been_run] = True

        # Return None to allow normal processing
        return None

    def _save_weight_for_controller(self, item: pytest.Item) -> None:
        weight_value = None
        for marker in item.iter_markers(name="weight"):
            if marker.args:
                weight_value = marker.args[0]
                break
        if weight_value is not None:
            item.user_properties.append((LoadTestPlugin.WEIGHT_PROPERTY_KEY, weight_value))

    def _cleanup_previous_run(self, item: pytest.Item) -> None:
        setupstate = item.session._setupstate

        # If item is in stack, run its teardown functions first
        if item in setupstate.stack:
            # Get the teardown functions
            finalizers, exc_info = setupstate.stack[item]

            # Run teardown functions in reverse order (LIFO)
            for finalizer in reversed(finalizers):
                try:
                    finalizer()
                except Exception as e:
                    logging.warning(f"Teardown error during re-execution for {item.nodeid}: {e}")

            # Now remove from stack
            del setupstate.stack[item]

        # Clear function-scoped fixture caches
        # Module/session fixtures keep their cache and persist
        self._clear_function_fixture_caches(item)

        # Clear funcargs - they will be repopulated during the setup phase
        funcargs = getattr(item, "funcargs", None)
        if funcargs is not None:
            funcargs.clear()

    def _clear_function_fixture_caches(self, item: pytest.Item) -> None:
        fixture_manager = item._request._fixturemanager  # type: ignore[attr-defined]
        if not fixture_manager:
            return

        # Get the fixture names used by this test
        fixture_info = item._fixtureinfo  # type: ignore[attr-defined]
        if not fixture_info or not hasattr(fixture_info, "argnames"):
            return

        CACHED_RESULT = "cached_result"

        # Iterate through all fixtures used by this test
        for fixture_name in fixture_info.argnames:
            # Skip the 'request' fixture - it's handled specially
            if fixture_name == "request":
                continue

            # Get fixture definitions for this name
            fixture_defs = fixture_manager.getfixturedefs(fixture_name, item.nodeid)
            if not fixture_defs:
                continue

            for fixture_def in fixture_defs:
                # Only clear function-scoped fixtures
                # Module/session fixtures persist across test runs
                if hasattr(fixture_def, "scope") and fixture_def.scope == "function":
                    if hasattr(fixture_def, CACHED_RESULT):
                        # Clear the cached result to force re-execution
                        setattr(fixture_def, CACHED_RESULT, None)

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_logreport(self, report: pytest.TestReport):
        """
        Hook called on controller when receiving test reports from workers.
        This is where we process skip reports, update weights, and track failures.
        """
        if not self.config or not self.is_enabled(self.config):
            return

        scheduler = self.config.stash.get(stash_key_scheduler, None)
        if not scheduler or not isinstance(scheduler, LoadTestScheduler):
            return

        # Check for stop signal and weight in user_properties
        if hasattr(report, "user_properties"):
            for key, value in report.user_properties:
                if key == LOAD_TEST_STOP_SIGNAL and isinstance(value, str):
                    scheduler.stop(value)
                elif key == LoadTestPlugin.WEIGHT_PROPERTY_KEY and isinstance(value, int):
                    # Update weight continuously as tests report them
                    if report.nodeid:
                        scheduler.update_weight(report.nodeid, value)

        # Process skip reports - handle both @pytest.mark.skip and pytest.skip() calls
        # Check all phases since skips can happen at different times
        if report.outcome == "skipped":
            if report.nodeid:
                scheduler.mark_test_skipped(report.nodeid)

        # Track failures and passes for circuit breaker (only on call phase)
        if report.when == "call":
            if report.nodeid:
                if report.outcome == "failed":
                    scheduler.mark_test_failed(report.nodeid)
                elif report.outcome == "passed":
                    scheduler.mark_test_passed(report.nodeid)

    def pytest_sessionstart(self, session: pytest.Session):
        """Hook called after Session object has been created and before test collection."""
        self.config = session.config
        session.config.stash[stash_key_session] = session

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int):
        """Hook called after whole test run finished, right before returning exit status."""
        # Print load test statistics if enabled
        if self.is_enabled(session.config):
            scheduler = session.config.stash.get(stash_key_scheduler, None)
            if scheduler:
                # Use stderr=False (logger) by default, can be changed to True for stderr output
                scheduler.print_final_statistics(use_stderr=True)

        if stash_key_session in session.config.stash:
            del session.config.stash[stash_key_session]


def pytest_configure(config: pytest.Config):
    """
    Register the plugin instance and custom markers.

    This is called once at the start of the pytest session.
    """
    # Register custom markers
    config.addinivalue_line(
        "markers", "weight(value): Set the weight of a test for load testing (higher = more likely to be selected)"
    )

    # Only register plugin instance if load testing is enabled
    if config.getoption(LoadTestPlugin.PYTEST_OPTION_NAME, False):
        plugin = LoadTestPlugin()
        config.pluginmanager.register(plugin, name="load_test_plugin")


def pytest_addoption(parser):
    """Add plugin-specific command line options."""
    group = parser.getgroup("xdist-load-testing")
    group.addoption(
        "--load-test",
        action="store_true",
        dest=LoadTestPlugin.PYTEST_OPTION_NAME,
        default=False,
        help="Enable load testing mode with continuous test execution.",
    )
