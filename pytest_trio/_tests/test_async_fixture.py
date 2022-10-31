import pytest


def test_single_async_fixture(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio

        @pytest.fixture
        async def fix1():
            await trio.sleep(0)
            return 'fix1'

        @pytest.mark.trio
        async def test_simple(fix1):
            assert fix1 == 'fix1'
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=1)


def test_async_fixture_recomputed_for_each_test(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio

        counter = 0

        @pytest.fixture
        async def fix1():
            global counter
            await trio.sleep(0)
            counter += 1
            return counter

        @pytest.mark.trio
        async def test_first(fix1):
            assert fix1 == 1

        @pytest.mark.trio
        async def test_second(fix1):
            assert fix1 == 2
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=2)


def test_nested_async_fixture(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio

        @pytest.fixture
        async def fix1():
            await trio.sleep(0)
            return 'fix1'

        @pytest.fixture
        async def fix2(fix1):
            await trio.sleep(0)
            return 'fix2(%s)' % fix1

        @pytest.mark.trio
        async def test_simple(fix2):
            assert fix2 == 'fix2(fix1)'

        @pytest.mark.trio
        async def test_both(fix1, fix2):
            assert fix1 == 'fix1'
            assert fix2 == 'fix2(fix1)'
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=2)


def test_async_within_sync_fixture(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio

        @pytest.fixture
        async def async_fix():
            await trio.sleep(0)
            return 42

        @pytest.fixture
        def sync_fix(async_fix):
            return async_fix

        @pytest.mark.trio
        async def test_simple(sync_fix):
            assert sync_fix == 42
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=1)


# In pytest, ERROR status occurs when an exception is raised in fixture code.
# The trouble is our async fixtures must be run within a trio context, hence
# they are actually run just before the test, providing no way to make the
# difference between an exception coming from the real test or from an
# async fixture...
@pytest.mark.xfail(reason="Not implemented yet")
def test_raise_in_async_fixture_cause_pytest_error(testdir):

    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture
        async def fix1():
            raise ValueError('Ouch !')

        @pytest.mark.trio
        async def test_base(fix1):
            pass  # Crash should have occurred before arriving here
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(errors=1)
