import trio
import functools


def test_timeout(testdir):
    testdir.makepyfile(
        """
        from trio import sleep
        import pytest
        import pytest_trio.timeout

        @pytest.mark.timeout(0.01)
        @pytest.mark.trio
        async def test_will_timeout():
            await sleep(10)
        """
    )

    testdir.makefile(".ini", pytest="[pytest]\ntrio_timeout=true\n")

    result = testdir.runpytest()

    result.stdout.fnmatch_lines(["Timeout reached"])
    result.assert_outcomes(failed=1)


def test_timeout_strict_exception_group(testdir, monkeypatch):
    monkeypatch.setattr(
        trio, "run", functools.partial(trio.run, strict_exception_groups=True)
    )

    testdir.makepyfile(
        """
        from trio import sleep
        import pytest
        import pytest_trio.timeout

        @pytest.mark.timeout(0.01)
        @pytest.mark.trio
        async def test_will_timeout():
            await sleep(10)
        """
    )

    testdir.makefile(".ini", pytest="[pytest]\ntrio_timeout=true\n")

    result = testdir.runpytest()

    result.stdout.fnmatch_lines(["Timeout reached"])
    result.assert_outcomes(failed=1)
