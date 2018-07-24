import pytest
from pytest_trio import trio_fixture


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

    result.assert_outcomes(passed=1, error=2)
    result.stdout.fnmatch_lines(
        ["*Trio fixtures can only be used by Trio tests*"]
    )


def test_trio_fixture_with_wrong_scope(testdir):
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
        import pytest_trio

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

    result.assert_outcomes(error=1)
    result.stdout.fnmatch_lines(["*must be function-scope*"])
