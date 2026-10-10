"""Test to reproduce the autouse async fixture bug."""
import pytest


def test_autouse_async_fixture_with_trio_mark(testdir):
    """Test that autouse=True async fixture runs with @pytest.mark.trio."""
    testdir.makepyfile(
        """
        import pytest
        import trio

        autouse_ran = []

        @pytest.fixture(autouse=True)
        async def autouse_fixture():
            await trio.sleep(0)
            autouse_ran.append(True)

        @pytest.mark.trio
        async def test_with_autouse():
            assert autouse_ran == [True]
    """
    )

    result = testdir.runpytest("-v", "-s")
    print("STDOUT:", result.stdout.str())
    print("STDERR:", result.stderr.str())
    result.assert_outcomes(passed=1)


def test_autouse_async_fixture_in_trio_mode(testdir):
    """Test that autouse=True async fixture runs in trio_mode."""
    testdir.makefile(".ini", pytest="[pytest]\ntrio_mode = true\n")
    testdir.makepyfile(
        """
        import pytest
        import trio

        autouse_ran = []

        @pytest.fixture(autouse=True)
        async def autouse_fixture():
            await trio.sleep(0)
            autouse_ran.append(True)

        async def test_with_autouse():
            assert autouse_ran == [True]
    """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_multiple_autouse_async_fixtures(testdir):
    """Test that multiple autouse=True async fixtures all run."""
    testdir.makepyfile(
        """
        import pytest
        import trio

        autouse_ran = []

        @pytest.fixture(autouse=True)
        async def autouse_fixture1():
            await trio.sleep(0)
            autouse_ran.append("fixture1")

        @pytest.fixture(autouse=True)
        async def autouse_fixture2():
            await trio.sleep(0)
            autouse_ran.append("fixture2")

        @pytest.mark.trio
        async def test_with_autouse():
            assert set(autouse_ran) == {"fixture1", "fixture2"}
    """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_autouse_async_fixture_with_dependency(testdir):
    """Test that autouse async fixture can depend on other fixtures."""
    testdir.makepyfile(
        """
        import pytest
        import trio

        autouse_ran = []
        regular_ran = []

        @pytest.fixture
        async def regular_fixture():
            await trio.sleep(0)
            regular_ran.append("regular")
            return "regular_value"

        @pytest.fixture(autouse=True)
        async def autouse_fixture(regular_fixture):
            await trio.sleep(0)
            autouse_ran.append(regular_fixture)

        @pytest.mark.trio
        async def test_with_autouse():
            assert regular_ran == ["regular"]
            assert autouse_ran == ["regular_value"]
    """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_autouse_async_yield_fixture(testdir):
    """Test that autouse=True async yield fixture runs setup and teardown."""
    testdir.makepyfile(
        """
        import pytest
        import trio

        autouse_ran = []

        @pytest.fixture(autouse=True)
        async def autouse_fixture():
            await trio.sleep(0)
            autouse_ran.append("setup")
            yield
            autouse_ran.append("teardown")

        @pytest.mark.trio
        async def test_with_autouse():
            assert autouse_ran == ["setup"]
    """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_autouse_async_fixture_with_regular_test_dependency(testdir):
    """Test that autouse async fixture works when test also has regular fixture deps."""
    testdir.makepyfile(
        """
        import pytest
        import trio

        autouse_ran = []
        regular_ran = []

        @pytest.fixture
        def regular_fixture():
            regular_ran.append("regular")
            return "regular_value"

        @pytest.fixture(autouse=True)
        async def autouse_fixture():
            await trio.sleep(0)
            autouse_ran.append("autouse")

        @pytest.mark.trio
        async def test_with_both(regular_fixture):
            assert regular_ran == ["regular"]
            assert autouse_ran == ["autouse"]
            assert regular_fixture == "regular_value"
    """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


if __name__ == "__main__":
    # Run with pytest directly for debugging
    import sys
    sys.exit(pytest.main([__file__, "-v"]))