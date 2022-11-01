import pytest


def test_async_test_is_executed(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio

        async_test_called = False

        @pytest.mark.trio
        async def test_base():
            global async_test_called
            await trio.sleep(0)
            async_test_called = True

        def test_check_async_test_called():
            assert async_test_called
    """
    )

    result = testdir.runpytest("-s")

    result.assert_outcomes(passed=2)


def test_async_test_as_class_method(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio

        async_test_called = False

        @pytest.fixture
        async def fix():
            await trio.sleep(0)
            return 'fix'

        class TestInClass:
            @pytest.mark.trio
            async def test_base(self, fix):
                global async_test_called
                assert fix == 'fix'
                await trio.sleep(0)
                async_test_called = True

        def test_check_async_test_called():
            assert async_test_called
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=2)


@pytest.mark.xfail(reason="Raises pytest internal error so far...")
def test_sync_function_with_trio_mark(testdir):

    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.trio
        def test_invalid():
            pass
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(errors=1)


def test_skip_and_xfail(testdir):

    testdir.makepyfile(
        """
        import functools
        import pytest
        import trio

        trio.run = functools.partial(trio.run, strict_exception_groups=True)

        @pytest.mark.trio
        async def test_xfail():
            pytest.xfail()

        @pytest.mark.trio
        async def test_skip():
            pytest.skip()

        async def callback(fn):
            fn()

        async def fail():
            raise RuntimeError

        @pytest.mark.trio
        async def test_xfail_and_fail():
            async with trio.open_nursery() as nursery:
                nursery.start_soon(callback, pytest.xfail)
                nursery.start_soon(fail)

        @pytest.mark.trio
        async def test_skip_and_fail():
            async with trio.open_nursery() as nursery:
                nursery.start_soon(callback, pytest.skip)
                nursery.start_soon(fail)

        @pytest.mark.trio
        async def test_xfail_and_skip():
            async with trio.open_nursery() as nursery:
                nursery.start_soon(callback, pytest.skip)
                nursery.start_soon(callback, pytest.xfail)
    """
    )

    result = testdir.runpytest("-s")

    result.assert_outcomes(skipped=1, xfailed=1, failed=3)
