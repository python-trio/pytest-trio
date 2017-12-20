import pytest


@pytest.fixture
def sync_fix():
    return 'sync_fix'


@pytest.mark.trio
async def test_single_sync_fixture(sync_fix):
    assert sync_fix == 'sync_fix'


def test_single_yield_fixture(testdir):

    testdir.makepyfile(
        """
        import pytest

        events = []

        @pytest.fixture
        def fix1():
            events.append('fixture setup')
            yield 'fix1'
            events.append('fixture teardown')

        def test_before():
            assert not events

        @pytest.mark.trio
        async def test_actual_test(fix1):
            assert events == ['fixture setup']
            assert fix1 == 'fix1'

        def test_after():
            assert events == [
                'fixture setup',
                'fixture teardown',
            ]
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=3)


def test_single_yield_fixture_with_async_deps(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio

        events = []

        @pytest.fixture
        async def fix0():
            events.append('fix0 setup')
            await trio.sleep(0)
            return 'fix0'

        @pytest.fixture
        def fix1(fix0):
            events.append('fix1 setup')
            yield 'fix1 - ' + fix0
            events.append('fix1 teardown')

        def test_before():
            assert not events

        @pytest.mark.trio
        async def test_actual_test(fix1):
            assert events == ['fix0 setup', 'fix1 setup']
            assert fix1 == 'fix1 - fix0'

        def test_after():
            assert events == [
                'fix0 setup',
                'fix1 setup',
                'fix1 teardown',
            ]
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=3)
