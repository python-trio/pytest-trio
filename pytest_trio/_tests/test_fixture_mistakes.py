import pytest
from pytest_trio import trio_fixture

from .helpers import enable_trio_mode


def test_trio_fixture_with_non_trio_test(testdir):
    testdir.makepyfile(
        """
        import trio
        from pytest_trio import trio_fixture
        import pytest

        @trio_fixture
        def trio_time():
            return trio.current_time()

        @pytest.fixture
        def indirect_trio_time(trio_time):
            return trio_time + 1

        @pytest.mark.trio
        async def test_async(mock_clock, trio_time, indirect_trio_time):
            assert trio_time == 0
            assert indirect_trio_time == 1

        def test_sync(trio_time):
            pass

        def test_sync_indirect(indirect_trio_time):
            pass
        """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=1, errors=2)
    result.stdout.fnmatch_lines(["*: Trio fixtures can only be used by Trio tests*"])


def test_trio_fixture_with_wrong_scope_without_trio_mode(testdir):
    # There's a trick here: when you have a non-function-scope fixture, it's
    # not instantiated for any particular function (obviously). So... when our
    # pytest_fixture_setup hook tries to check for marks, it can't normally
    # see @pytest.mark.trio. So... it's actually almost impossible to have an
    # async fixture get treated as a Trio fixture *and* have it be
    # non-function-scope. But, class-scoped fixtures can see marks on the
    # class, so this is one way (the only way?) it can happen:
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="class")
        async def async_class_fixture():
            pass

        @pytest.mark.trio
        class TestFoo:
            async def test_foo(self, async_class_fixture):
                pass
        """
    )

    result = testdir.runpytest()

    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*: Trio fixtures must be function-scope*"])


@enable_trio_mode
def test_trio_fixture_with_wrong_scope_in_trio_mode(testdir, enable_trio_mode):
    enable_trio_mode(testdir)

    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="session")
        async def async_session_fixture():
            pass


        async def test_whatever(async_session_fixture):
            pass
        """
    )

    result = testdir.runpytest()

    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*: Trio fixtures must be function-scope*"])


@enable_trio_mode
def test_async_fixture_with_sync_test_in_trio_mode(testdir, enable_trio_mode):
    enable_trio_mode(testdir)

    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture
        async def async_fixture():
            pass


        def test_whatever(async_fixture):
            pass
        """
    )

    result = testdir.runpytest()

    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*: Trio fixtures can only be used by Trio tests*"])


@enable_trio_mode
def test_fixture_cancels_test_but_doesnt_raise(testdir, enable_trio_mode):
    enable_trio_mode(testdir)

    testdir.makepyfile(
        """
        import pytest
        import trio

        @pytest.fixture
        async def async_fixture():
            with trio.CancelScope() as cscope:
                cscope.cancel()
                yield


        async def test_whatever(async_fixture):
            pass
        """
    )

    result = testdir.runpytest()

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*async_fixture*cancelled the test*"])


@enable_trio_mode
def test_too_many_clocks(testdir, enable_trio_mode):
    enable_trio_mode(testdir)

    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture
        def extra_clock(mock_clock):
            return mock_clock

        async def test_whatever(mock_clock, extra_clock):
            pass
        """
    )

    result = testdir.runpytest()

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(
        ["*ValueError: Expected at most one Clock in kwargs, got *"]
    )
