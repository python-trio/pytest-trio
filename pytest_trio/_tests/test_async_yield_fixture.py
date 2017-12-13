import sys
import pytest


@pytest.mark.skipif(sys.version_info < (3, 6), reason="requires python3.6")
def test_single_async_yield_fixture(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio

        events = []

        @pytest.fixture
        async def fix1():
            events.append('fix1 setup')
            await trio.sleep(0)

            yield 'fix1'

            await trio.sleep(0)
            events.append('fix1 teardown')

        def test_before():
            assert not events

        @pytest.mark.trio
        async def test_actual_test(fix1):
            assert events == ['fix1 setup']
            assert fix1 == 'fix1'

        def test_after():
            assert events == [
                'fix1 setup',
                'fix1 teardown',
            ]
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=3)


@pytest.mark.skipif(sys.version_info < (3, 6), reason="requires python3.6")
def test_nested_async_yield_fixture(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio

        events = []

        @pytest.fixture
        async def fix2():
            events.append('fix2 setup')
            await trio.sleep(0)

            yield 'fix2'

            await trio.sleep(0)
            events.append('fix2 teardown')

        @pytest.fixture
        async def fix1(fix2):
            events.append('fix1 setup')
            await trio.sleep(0)

            yield 'fix1'

            await trio.sleep(0)
            events.append('fix1 teardown')

        def test_before():
            assert not events

        @pytest.mark.trio
        async def test_actual_test(fix1):
            assert events == [
                'fix2 setup',
                'fix1 setup',
            ]
            assert fix1 == 'fix1'

        def test_after():
            assert events == [
                'fix2 setup',
                'fix1 setup',
                'fix1 teardown',
                'fix2 teardown',
            ]
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=3)


@pytest.mark.skipif(sys.version_info < (3, 6), reason="requires python3.6")
def test_async_yield_fixture_within_sync_fixture(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio

        events = []

        @pytest.fixture
        async def fix2():
            events.append('fix2 setup')
            await trio.sleep(0)

            yield 'fix2'

            await trio.sleep(0)
            events.append('fix2 teardown')

        @pytest.fixture
        def fix1(fix2):
            return 'fix1'

        def test_before():
            assert not events

        @pytest.mark.trio
        async def test_actual_test(fix1):
            assert events == [
                'fix2 setup',
            ]
            assert fix1 == 'fix1'

        def test_after():
            assert events == [
                'fix2 setup',
                'fix2 teardown',
            ]
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=3)


@pytest.mark.skipif(sys.version_info < (3, 6), reason="requires python3.6")
def test_async_yield_fixture_within_sync_yield_fixture(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio

        events = []

        @pytest.fixture
        async def fix2():
            events.append('fix2 setup')
            await trio.sleep(0)

            yield 'fix2'

            await trio.sleep(0)
            events.append('fix2 teardown')

        @pytest.fixture
        def fix1(fix2):
            events.append('fix1 setup')
            yield 'fix1'
            events.append('fix1 teardown')

        def test_before():
            assert not events

        @pytest.mark.trio
        async def test_actual_test(fix1):
            assert events == [
                'fix2 setup',
                'fix1 setup',
            ]
            assert fix1 == 'fix1'

        def test_after():
            assert events == [
                'fix2 setup',
                'fix1 setup',
                'fix1 teardown',
                'fix2 teardown',
            ]
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=3)


@pytest.mark.skipif(sys.version_info < (3, 6), reason="requires python3.6")
def test_async_yield_fixture_with_multiple_yields(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio

        @pytest.fixture
        async def fix1():
            await trio.sleep(0)
            yield 'good'
            await trio.sleep(0)
            yield 'bad'

        @pytest.mark.trio
        async def test_actual_test(fix1):
            pass
    """
    )

    result = testdir.runpytest()

    # TODO: should trigger error instead of failure
    # result.assert_outcomes(error=1)
    result.assert_outcomes(failed=1)
