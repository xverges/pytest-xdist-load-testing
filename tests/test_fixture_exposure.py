"""Test that the plugin exposes the expected fixtures."""


def test_shared_json_fixture_factory_is_exposed(pytester):
    """Verify that shared_json_fixture_factory fixture is available."""
    pytester.makepyfile(
        """
        def test_fixture_exists(shared_json_fixture_factory):
            # If fixture doesn't exist, this test will fail with fixture not found error
            assert callable(shared_json_fixture_factory)
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_rate_limiter_fixture_factory_is_exposed(pytester):
    """Verify that rate_limiter_fixture_factory fixture is available."""
    pytester.makepyfile(
        """
        def test_fixture_exists(rate_limiter_fixture_factory):
            # If fixture doesn't exist, this test will fail with fixture not found error
            assert callable(rate_limiter_fixture_factory)
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_both_fixtures_work_together(pytester):
    """Verify that both fixtures can be used in the same test."""
    pytester.makepyfile(
        """
        def test_both_fixtures(shared_json_fixture_factory, rate_limiter_fixture_factory):
            assert callable(shared_json_fixture_factory)
            assert callable(rate_limiter_fixture_factory)
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_fixtures_are_session_scoped(pytester):
    """Verify that fixtures have session scope."""
    pytester.makepyfile(
        """
        import pytest

        def test_shared_json_scope(request):
            fixture_def = request._fixturemanager.getfixturedefs(
                'shared_json_fixture_factory', request.node
            )[0]
            assert fixture_def.scope == 'session'

        def test_rate_limiter_scope(request):
            fixture_def = request._fixturemanager.getfixturedefs(
                'rate_limiter_fixture_factory', request.node
            )[0]
            assert fixture_def.scope == 'session'
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=2)


def test_fixtures_available_even_without_load_test_flag(pytester):
    """Verify fixtures are available even without --load-test flag.

    The fixtures are registered unconditionally so they can be used
    in regular pytest runs, not just load testing mode.
    """
    pytester.makepyfile(
        """
        def test_fixture_exists(shared_json_fixture_factory):
            # Fixtures should be available even without --load-test
            assert callable(shared_json_fixture_factory)
        """
    )
    # Run without --load-test flag
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_all_expected_fixtures_exposed(pytester):
    """Test that all expected fixtures are exposed by the plugin."""
    pytester.makepyfile(
        """
        import pytest

        EXPECTED_FIXTURES = [
            'shared_json_fixture_factory',
            'rate_limiter_fixture_factory',
        ]

        def test_all_fixtures_present(request):
            fixture_manager = request._fixturemanager
            available_fixtures = set(fixture_manager._arg2fixturedefs.keys())

            for fixture_name in EXPECTED_FIXTURES:
                assert fixture_name in available_fixtures, (
                    f"Expected fixture '{fixture_name}' not found. "
                    f"Available fixtures: {sorted(available_fixtures)}"
                )
        """
    )
    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)
