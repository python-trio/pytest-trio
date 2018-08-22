import pytest
from pytest_trio import trio_fixture

import contextvars

cv = contextvars.ContextVar("cv", default=None)


@trio_fixture
def cv_checker():
    assert cv.get() is None
    yield
    assert cv.get() is None


@trio_fixture
def cv_setter(cv_checker):
    assert cv.get() is None
    token = cv.set("cv_setter")
    yield
    assert cv.get() == "cv_setter2"
    cv.reset(token)
    assert cv.get() is None


@trio_fixture
def cv_setter2(cv_setter):
    assert cv.get() == "cv_setter"
    # Intentionally leak, so can check that this is visible back in cv_setter
    cv.set("cv_setter2")
    yield
    assert cv.get() == "cv_setter2"


@pytest.mark.trio
async def test_contextvars(cv_setter2):
    assert cv.get() == "cv_setter2"
