import pytest

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


def test_trio_mode_pytest_ini(testdir):
    testdir.makepyfile(test_text)

    testdir.makefile(".ini", pytest="[pytest]\ntrio_mode = true\n")

    result = testdir.runpytest()
    result.assert_outcomes(passed=2, failed=2)


def test_trio_mode_conftest(testdir):
    testdir.makepyfile(test_text)

    testdir.makeconftest("from pytest_trio.enable_trio_mode import *")

    result = testdir.runpytest()
    result.assert_outcomes(passed=2, failed=2)
