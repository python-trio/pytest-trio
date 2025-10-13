import pytest  # noqa: F401

from .helpers import enable_trio_mode

test_text = """
import pytest
import trio
from hypothesis import given, settings, strategies

async def test_pass():
    await trio.sleep(0)

async def test_fail():
    await trio.sleep(0)
    assert False

@settings(deadline=None, max_examples=5)
@given(strategies.binary())
async def test_hypothesis_pass(b):
    await trio.sleep(0)
    assert isinstance(b, bytes)

@settings(deadline=None, max_examples=5)
@given(strategies.binary())
async def test_hypothesis_fail(b):
    await trio.sleep(0)
    assert isinstance(b, int)
"""


@enable_trio_mode
def test_trio_mode(testdir, enable_trio_mode):
    enable_trio_mode(testdir)

    testdir.makepyfile(test_text)

    result = testdir.runpytest()
    result.assert_outcomes(passed=2, failed=2)


# This is faking qtrio due to real qtrio's dependence on either
# PyQt5 or PySide2.  They are both large and require special
# handling in CI.  The testing here is able to focus on the
# pytest-trio features with just this minimal substitute.
qtrio_text = """
import trio

fake_used = False

def run(*args, **kwargs):
    global fake_used
    fake_used = True

    return trio.run(*args, **kwargs)
"""


# Fake trio_asyncio module.
trio_asyncio_text = qtrio_text


def test_trio_mode_and_qtrio_run_configuration(testdir):
    testdir.makefile(".ini", pytest="[pytest]\ntrio_mode = true\ntrio_run = qtrio\n")

    testdir.makepyfile(qtrio=qtrio_text)

    test_text = """
    import qtrio
    import trio

    async def test_fake_qtrio_used():
        await trio.sleep(0)
        assert qtrio.fake_used
    """
    testdir.makepyfile(test_text)

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_trio_mode_and_qtrio_marker(testdir):
    testdir.makefile(".ini", pytest="[pytest]\ntrio_mode = true\n")

    testdir.makepyfile(qtrio=qtrio_text)

    test_text = """
    import pytest
    import qtrio
    import trio

    @pytest.mark.trio(run=qtrio.run)
    async def test_fake_qtrio_used():
        await trio.sleep(0)
        assert qtrio.fake_used
    """
    testdir.makepyfile(test_text)

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_qtrio_just_run_configuration(testdir):
    testdir.makefile(".ini", pytest="[pytest]\ntrio_run = qtrio\n")

    testdir.makepyfile(qtrio=qtrio_text)

    test_text = """
    import pytest
    import qtrio
    import trio

    @pytest.mark.trio
    async def test_fake_qtrio_used():
        await trio.sleep(0)
        assert qtrio.fake_used
    """
    testdir.makepyfile(test_text)

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_trio_asyncio_just_run_configuration(testdir):
    testdir.makefile(".ini", pytest="[pytest]\ntrio_run = trio_asyncio\n")

    testdir.makepyfile(trio_asyncio=trio_asyncio_text)

    test_text = """
    import pytest
    import trio_asyncio
    import trio

    @pytest.mark.trio
    async def test_fake_trio_asyncio_used():
        await trio.sleep(0)
        assert trio_asyncio.fake_used
    """
    testdir.makepyfile(test_text)

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_invalid_trio_run_fails(testdir):
    run_name = "invalid_trio_run"

    testdir.makefile(
        ".ini", pytest=f"[pytest]\ntrio_mode = true\ntrio_run = {run_name}\n"
    )

    test_text = """
    async def test():
        pass
    """
    testdir.makepyfile(test_text)

    result = testdir.runpytest()
    result.assert_outcomes()
    result.stdout.fnmatch_lines(
        [
            f"*ValueError: {run_name!r} not valid for 'trio_run' config.  Must be one of: *"
        ]
    )


def test_closest_explicit_run_wins(testdir):
    testdir.makefile(".ini", pytest="[pytest]\ntrio_mode = true\ntrio_run = trio\n")
    testdir.makepyfile(qtrio=qtrio_text)

    test_text = """
    import pytest
    import pytest_trio
    import qtrio

    @pytest.mark.trio(run='should be ignored')
    @pytest.mark.trio(run=qtrio.run)
    async def test():
        assert qtrio.fake_used
    """
    testdir.makepyfile(test_text)

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_ini_run_wins_with_blank_marker(testdir):
    testdir.makefile(".ini", pytest="[pytest]\ntrio_mode = true\ntrio_run = qtrio\n")
    testdir.makepyfile(qtrio=qtrio_text)

    test_text = """
    import pytest
    import pytest_trio
    import qtrio

    @pytest.mark.trio
    async def test():
        assert qtrio.fake_used
    """
    testdir.makepyfile(test_text)

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)
