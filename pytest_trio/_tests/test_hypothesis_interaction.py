import pytest
from hypothesis import given, settings, strategies as st

# To avoid unpredictable warnings/errors when CI happens to be slow
# Example: https://travis-ci.org/python-trio/pytest-trio/jobs/406738296
our_settings = settings(deadline=None)


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
