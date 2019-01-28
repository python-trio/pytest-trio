import pytest
import trio
from hypothesis import given, settings, strategies as st

from pytest_trio.plugin import _trio_test_runner_factory

# deadline=None avoids unpredictable warnings/errors when CI happens to be
# slow (example: https://travis-ci.org/python-trio/pytest-trio/jobs/406738296)
# max_examples=5 speeds things up a bit
our_settings = settings(deadline=None, max_examples=5)


@our_settings
@given(st.integers())
@pytest.mark.trio
async def test_mark_inner(n):
    assert isinstance(n, int)


@our_settings
@pytest.mark.trio
@given(st.integers())
async def test_mark_outer(n):
    assert isinstance(n, int)


@our_settings
@pytest.mark.parametrize('y', [1, 2])
@given(x=st.none())
@pytest.mark.trio
async def test_mark_and_parametrize(x, y):
    assert x is None
    assert y in (1, 2)


async def scheduler_trace():
    """Returns a scheduler-dependent value we can use to check determinism."""
    trace = []

    async def tracer(name):
        for i in range(10):
            trace.append((name, i))
            await trio.sleep(0)

    async with trio.open_nursery() as nursery:
        for i in range(5):
            nursery.start_soon(tracer, i)

    return tuple(trace)


def test_the_trio_scheduler_is_not_deterministic():
    # At least, not yet.  See https://github.com/python-trio/trio/issues/32
    traces = []
    for _ in range(10):
        traces.append(trio.run(scheduler_trace))
    assert len(set(traces)) == len(traces)


def test_the_trio_scheduler_is_deterministic_under_hypothesis():
    traces = []

    @our_settings
    @given(st.integers())
    @pytest.mark.trio
    async def inner(_):
        traces.append(await scheduler_trace())

    # The pytest.mark.trio doesn't do it's magic thing to
    # inner functions, so we invoke it explicitly here.
    inner.hypothesis.inner_test = _trio_test_runner_factory(
        None, inner.hypothesis.inner_test
    )
    inner()  # Tada, now it's a sync function!

    assert len(traces) >= 5
    assert len(set(traces)) == 1
