"""Load testing scheduler implementation."""
import logging
import random
import time
from typing import Any, Optional

import pytest
from xdist.scheduler import LoadScheduling
from xdist.workermanage import WorkerController

from .constants import stash_key_session

logger = logging.getLogger(__name__)


class LoadTestScheduler(LoadScheduling):
    """
    Custom scheduler for pytest-xdist that continuously supplies tests to workers.

    Extends LoadScheduling to provide weighted random test selection for load testing.
    Tests are selected randomly based on their weights, allowing for load testing
    scenarios where certain tests should be run more frequently than others.

    Weights are collected continuously as tests run and updated in real-time.
    Initially all tests have weight 1, then as tests report their weights via
    user_properties, the weights are updated for future scheduling decisions.
    """

    class LogProducer:
        """
        Compatible with xdist's Producer interface but routes messages through
        Python's logging system.
        """
        def __init__(self, name: str, *, enabled: bool = True) -> None:
            self.name = name
            self.enabled = enabled

        def __repr__(self) -> str:
            return f"{type(self).__name__}({self.name!r}, enabled={self.enabled})"

        def __call__(self, *a: Any, **k: Any) -> None:
            if self.enabled:
                message = " ".join(str(arg) for arg in a)
                logger.info(message)

        def __getattr__(self, name: str) -> "LoadTestScheduler.LogProducer":
            return type(self)(name, enabled=self.enabled)

    def __init__(self, config, log=None):
        custom_log = self.LogProducer("load_test_scheduler")
        super().__init__(config, custom_log)  # type: ignore[arg-type]
        self.weights = []  # Current weights for each test (updated as we learn them)
        self.interrupted = False
        self.interrupt_reason = None
        self.config = config
        # Track test execution statistics
        self.test_passes = {}  # nodeid -> pass count
        self.test_failures = {}  # nodeid -> failure count
        self.last_success_time = {}  # nodeid -> timestamp of last success

    def _initialize_weights(self) -> None:
        """Initialize weights to 1 for all tests in collection."""
        if self.collection and not self.weights:
            # Start with weight 1 for all tests
            self.weights = [1] * len(self.collection)
            self.log(f"Initialized weights to 1 for {len(self.collection)} tests")

    def update_weight(self, nodeid: str, weight: int) -> None:
        """Update the weight for a specific test."""
        if not self.collection:
            return

        try:
            index = self.collection.index(nodeid)
            if 0 <= index < len(self.weights):
                old_weight = self.weights[index]
                if old_weight == 0:
                    self.log(f"Skipping weight update for {nodeid} (test is skipped)")
                    return
                self.weights[index] = weight
                self.log(f"Updated weight for {nodeid}: {old_weight} -> {weight}")
        except (ValueError, IndexError):
            pass

    def _validate_single_module(self) -> bool:
        """
        Validate that all collected tests are from a single module.

        Load testing is designed to work with a single module to ensure
        proper fixture handling and test isolation.

        Returns:
            True if all tests are from a single module, False otherwise
        """
        if not self.collection:
            return True

        # Extract module paths from nodeids (everything before ::)
        modules = set()
        for nodeid in self.collection:
            # nodeid format: path/to/test_file.py::TestClass::test_method
            # or: path/to/test_file.py::test_function
            module_path = nodeid.split("::")[0]
            modules.add(module_path)

        if len(modules) > 1:
            module_list = "\n  - ".join(sorted(modules))
            error_msg = (
                f"Load testing requires tests from a single module only.\n"
                f"Found tests from {len(modules)} different modules:\n"
                f"  - {module_list}\n"
                f"\n"
                f"Please specify a single test module when using --load-test.\n"
                f"Example: pytest --load-test -n 4 path/to/test_module.py"
            )
            # Use pytest.exit to properly terminate with error message
            pytest.exit(error_msg, returncode=1)

        return True

    def check_schedule(self, node: WorkerController, duration: float = 0) -> None:
        """
        Override to implement continuous weighted test selection.

        Tests are selected randomly based on their current weights.
        Weights start at 1 and are updated as tests report their weights.
        """
        # Check if session has requested stop
        session = self.config.stash.get(stash_key_session, None)
        if session is not None and session.shouldstop:
            if not self.interrupted:
                self.stop(str(session.shouldstop))
            return

        if self.interrupted or node.shutting_down:
            return

        # If we don't have a collection yet, use parent's logic
        if not self.collection:
            super().check_schedule(node, duration)
            return

        # Ensure weights are initialized
        if not self.weights:
            self._initialize_weights()

        # Continuous weighted distribution
        node_pending = self.node2pending[node]

        # Keep the node busy with at least 2 tests
        min_pending = 2
        if len(node_pending) < min_pending:
            # Send more tests - select randomly based on current weights
            num_to_send = min_pending - len(node_pending)
            self._send_weighted_tests(node, num_to_send)

    def _send_weighted_tests(self, node: WorkerController, num: int) -> None:
        """Send tests to a node, selected randomly based on weights."""
        if not self.collection or not self.weights:
            return

        # Check if all weights are zero (all tests skipped)
        if all(w == 0 for w in self.weights):
            self.log("All tests have weight 0 (skipped), stopping scheduler")
            # Use pytest.exit to properly terminate without internal errors
            pytest.exit("All tests are being skipped", returncode=2)

        # Select 'num' tests randomly with weights
        # Tests with weight 0 will never be selected
        try:
            selected_indices = random.choices(
                range(len(self.collection)),
                weights=self.weights,
                k=num
            )
        except ValueError:
            # This shouldn't happen if we checked for all-zero weights above
            self.log("Error selecting tests with weights, stopping scheduler")
            self.stop("Weight selection error")
            return

        # Add to node's pending list and send
        self.node2pending[node].extend(selected_indices)
        node.send_runtest_some(selected_indices)

    def schedule(self) -> None:
        """
        Initiate distribution of tests for load testing.

        Continuous weighted distribution: tests are selected randomly based on
        their current weights, which are updated as tests run and report weights.
        """
        if not self.collection_is_completed:
            return

        # First time setup
        if self.collection is None:
            # Use parent's collection validation
            if not self._check_nodes_have_same_collection():
                self.log("**Different tests collected, aborting run**")
                return

            self.collection = next(iter(self.node2collection.values()))
            if not self.collection:
                return

            # Validate that all tests are from a single module
            if not self._validate_single_module():
                return

        # Initialize weights with default value of 1
        self._initialize_weights()

        # Start scheduling on all nodes
        for node in self.nodes:
            self.check_schedule(node)

    def mark_test_complete(
        self, node: WorkerController, item_index: int, duration: float = 0
    ) -> None:
        """Called when a test completes - schedule more work."""
        # Call parent, which will call check_schedule
        super().mark_test_complete(node, item_index, duration)

    def mark_test_failed(self, nodeid: str) -> None:
        """
        Track test failure statistics.

        Args:
            nodeid: The node ID of the test that failed
        """
        if not self.collection:
            return

        # Increment failure count for this test
        self.test_failures[nodeid] = self.test_failures.get(nodeid, 0) + 1
        self.log(f"Test {nodeid} failed (total failures: {self.test_failures[nodeid]})")

    def mark_test_passed(self, nodeid: str) -> None:
        """
        Track test pass statistics and update last success timestamp.

        Args:
            nodeid: The node ID of the test that passed
        """
        if not self.collection:
            return

        # Increment pass count and update last success time
        self.test_passes[nodeid] = self.test_passes.get(nodeid, 0) + 1
        self.last_success_time[nodeid] = time.time()
        self.log(f"Test {nodeid} passed (total passes: {self.test_passes[nodeid]})")

    def mark_test_skipped(self, nodeid: str) -> None:
        """
        Mark a test as skipped by setting its weight to zero.

        Tests with weight 0 will never be selected during weighted distribution.

        Args:
            nodeid: The node ID of the test that was skipped
        """
        if not self.collection:
            return

        try:
            item_index = self.collection.index(nodeid)
            if 0 <= item_index < len(self.weights):
                if self.weights[item_index] != 0:
                    self.weights[item_index] = 0
                    self.log(f"Set weight to 0 for {nodeid} - will not be re-scheduled")

                    # Count how many tests have weight 0
                    zero_weight_count = sum(1 for w in self.weights if w == 0)
                    self.log(f"Total tests with weight 0: {zero_weight_count}/{len(self.weights)}")
        except (ValueError, IndexError):
            pass

    def remove_node(self, node: WorkerController) -> Optional[str]:
        """Called when a worker node is removed."""
        # For load testing, we don't reschedule crashed items
        # Just remove the node
        pending = self.node2pending.pop(node, [])
        self.node2collection.pop(node, None)

        if pending:
            # Return the first item that was running
            return self.collection[pending[0]] if self.collection else None
        return None

    def stop(self, reason: str = "Interrupted"):
        """Stop the scheduler and shut down all nodes."""
        self.interrupted = True
        self.interrupt_reason = reason
        self.log(f"Load testing stopped: {reason}")

        session = self.config.stash.get(stash_key_session, None)
        if session is not None:
            session.shouldstop = reason

        # Shutdown all nodes
        for node in self.nodes:
            if not node.shutting_down:
                node.shutdown()
