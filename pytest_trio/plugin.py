"""pytest-trio implementation."""
import sys
from traceback import format_exception
from collections.abc import Coroutine, Generator
from inspect import iscoroutinefunction, isgeneratorfunction
import pytest
import trio
from trio.testing import MockClock, trio_test
from async_generator import (
    async_generator, yield_, asynccontextmanager, isasyncgen,
    isasyncgenfunction
)

################################################################
# Basic setup
################################################################

if sys.version_info >= (3, 6):
    ORDERED_DICTS = True
else:
    # Ordered dict (and **kwargs) not available with Python<3.6
    ORDERED_DICTS = False


def pytest_addoption(parser):
    parser.addini(
        "trio_mode",
        "should pytest-trio handle all async functions?",
        type="bool",
        default=False,
    )


def pytest_configure(config):
    # So that it shows up in 'pytest --markers' output:
    config.addinivalue_line(
        "markers", "trio: "
        "mark the test as an async trio test; "
        "it will be run using trio.run"
    )


@pytest.hookimpl(tryfirst=True)
def pytest_exception_interact(node, call, report):
    if issubclass(call.excinfo.type, trio.MultiError):
        # TODO: not really elegant (pytest cannot output color with this hack)
        report.longrepr = ''.join(format_exception(*call.excinfo._excinfo))


################################################################
# Core support for running tests and constructing fixtures
################################################################


def _trio_test_runner_factory(item, testfunc=None):
    testfunc = testfunc or item.function

    if getattr(testfunc, '_trio_test_runner_wrapped', False):
        # We have already wrapped this, perhaps because we combined Hypothesis
        # with pytest.mark.parametrize
        return testfunc

    if not iscoroutinefunction(testfunc):
        pytest.fail(
            'test function `%r` is marked trio but is not async' % item
        )

    @trio_test
    async def _bootstrap_fixture_and_run_test(**kwargs):
        __tracebackhide__ = True
        user_exc = None
        # Open the nursery exposed as fixture
        async with trio.open_nursery() as nursery:
            item._trio_nursery = nursery
            try:
                async with _setup_async_fixtures_in(kwargs) as resolved_kwargs:
                    try:
                        await testfunc(**resolved_kwargs)
                    except BaseException as exc:
                        # Regular pytest fixture don't have access to the test
                        # exception in there teardown, we mimic this behavior
                        # here.
                        user_exc = exc
            except BaseException as exc:
                # If we are here, the exception comes from the fixtures setup
                # or teardown
                if user_exc:
                    raise exc from user_exc
                else:
                    raise exc
            finally:
                # No matter what the nursery fixture should be closed when
                # test is over
                nursery.cancel_scope.cancel()

        # Finally re-raise or original exception coming from the test if
        # needed
        if user_exc:
            raise user_exc

    _bootstrap_fixture_and_run_test._trio_test_runner_wrapped = True
    return _bootstrap_fixture_and_run_test


@asynccontextmanager
@async_generator
async def _setup_async_fixtures_in(deps):
    __tracebackhide__ = True

    need_resolved_deps_stack = [
        (k, v) for k, v in deps.items() if isinstance(v, TrioFixture)
    ]
    if not ORDERED_DICTS:
        # Make the fixture resolution order determinist
        need_resolved_deps_stack = sorted(need_resolved_deps_stack)

    if not need_resolved_deps_stack:
        await yield_(deps)
        return

    @asynccontextmanager
    @async_generator
    async def _recursive_setup(deps_stack):
        __tracebackhide__ = True
        name, dep = deps_stack.pop()
        async with dep.setup() as resolved:
            if not deps_stack:
                await yield_([(name, resolved)])
            else:
                async with _recursive_setup(deps_stack
                                            ) as remains_deps_stack_resolved:
                    await yield_(
                        remains_deps_stack_resolved + [(name, resolved)]
                    )

    async with _recursive_setup(need_resolved_deps_stack
                                ) as resolved_deps_stack:
        await yield_({**deps, **dict(resolved_deps_stack)})


class TrioFixture:
    """
    Represent a fixture that need to be run in a trio context to be resolved.
    """

    def __init__(self, fixturedef, deps={}):
        self.fixturedef = fixturedef
        self.deps = deps
        self.setup_done = False
        self.result = None

    @asynccontextmanager
    @async_generator
    async def setup(self):
        __tracebackhide__ = True
        if self.setup_done:
            await yield_(self.result)
        else:
            async with _setup_async_fixtures_in(self.deps) as resolved_deps:
                retval = self.fixturedef.func(**resolved_deps)
                if isinstance(retval, Coroutine):
                    self.result = await retval
                elif isasyncgen(retval):
                    self.result = await retval.asend(None)
                elif isinstance(retval, Generator):
                    self.result = retval.send(None)
                else:
                    # Regular synchronous function
                    self.result = retval

                try:
                    await yield_(self.result)
                finally:
                    if isasyncgen(retval):
                        try:
                            await retval.asend(None)
                        except StopAsyncIteration:
                            pass
                        else:
                            raise RuntimeError("too many yields in fixture")
                    elif isinstance(retval, Generator):
                        try:
                            retval.send(None)
                        except StopIteration:
                            pass
                        else:
                            raise RuntimeError("too many yields in fixture")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    if item.get_closest_marker("trio") is not None:
        if hasattr(item.obj, 'hypothesis'):
            # If it's a Hypothesis test, we go in a layer.
            item.obj.hypothesis.inner_test = _trio_test_runner_factory(
                item, item.obj.hypothesis.inner_test
            )
        elif getattr(item.obj, 'is_hypothesis_test', False):
            pytest.fail(
                'test function `%r` is using Hypothesis, but pytest-trio '
                'only works with Hypothesis 3.64.0 or later.' % item
            )
        else:
            item.obj = _trio_test_runner_factory(item)

    yield


# It's intentionally impossible to use this to create a non-function-scoped
# fixture (since that would require exposing a way to pass scope= to
# pytest.fixture).
def trio_fixture(func):
    func._force_trio_fixture = True
    return pytest.fixture(func)


def _is_trio_fixture(func, is_trio_test, deps):
    if getattr(func, "_force_trio_fixture", False):
        return True
    if is_trio_test:
        if iscoroutinefunction(func) or isasyncgenfunction(func):
            return True
    if any(isinstance(dep, TrioFixture) for dep in deps.values()):
        return True
    return False


@pytest.hookimpl
def pytest_fixture_setup(fixturedef, request):
    is_trio_test = (request.node.get_closest_marker("trio") is not None)
    deps = {dep: request.getfixturevalue(dep) for dep in fixturedef.argnames}
    if _is_trio_fixture(fixturedef.func, is_trio_test, deps):
        if request.scope != "function":
            raise RuntimeError("Trio fixtures must be function-scope")
        if not is_trio_test:
            raise RuntimeError("Trio fixtures can only be used by Trio tests")
        fixture = TrioFixture(fixturedef, deps)
        fixturedef.cached_result = (fixture, request.param_index, None)
        return fixture


################################################################
# Trio mode
################################################################


def automark(items):
    for item in items:
        if hasattr(item.obj, "hypothesis"):
            test_func = item.obj.hypothesis.inner_test
        else:
            test_func = item.obj
        if iscoroutinefunction(test_func):
            item.add_marker(pytest.mark.trio)


def pytest_collection_modifyitems(config, items):
    if config.getini("trio_mode"):
        automark(items)


################################################################
# Built-in fixtures
################################################################


@pytest.fixture
def mock_clock():
    return MockClock()


@pytest.fixture
def autojump_clock():
    return MockClock(autojump_threshold=0)


@trio_fixture
def nursery(request):
    return request.node._trio_nursery
