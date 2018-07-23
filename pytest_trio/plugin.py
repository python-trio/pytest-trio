"""pytest-trio implementation."""
import sys
from traceback import format_exception
from inspect import iscoroutinefunction, isgeneratorfunction
import pytest
import trio
from trio.testing import MockClock, trio_test
from async_generator import (
    async_generator, yield_, asynccontextmanager, isasyncgenfunction
)

################################################################
# Basic setup
################################################################

if sys.version_info >= (3, 6):
    ORDERED_DICTS = True
else:
    # Ordered dict (and **kwargs) not available with Python<3.6
    ORDERED_DICTS = False


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
        (k, v) for k, v in deps.items() if isinstance(v, BaseAsyncFixture)
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


class BaseAsyncFixture:
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
                async with self._setup(resolved_deps) as self.result:
                    self.setup_done = True
                    await yield_(self.result)

    async def _setup(self):
        raise NotImplementedError()


class AsyncYieldFixture(BaseAsyncFixture):
    """
    Async generator fixture.
    """

    @asynccontextmanager
    @async_generator
    async def _setup(self, resolved_deps):
        __tracebackhide__ = True
        agen = self.fixturedef.func(**resolved_deps)

        try:
            await yield_(await agen.asend(None))
        finally:
            try:
                await agen.asend(None)
            except StopAsyncIteration:
                pass
            else:
                raise RuntimeError('Only one yield in fixture is allowed')


class SyncFixtureWithAsyncDeps(BaseAsyncFixture):
    """
    Synchronous function fixture with asynchronous dependencies fixtures.
    """

    @asynccontextmanager
    @async_generator
    async def _setup(self, resolved_deps):
        __tracebackhide__ = True
        await yield_(self.fixturedef.func(**resolved_deps))


class SyncYieldFixtureWithAsyncDeps(BaseAsyncFixture):
    """
    Synchronous generator fixture with asynchronous dependencies fixtures.
    """

    @asynccontextmanager
    @async_generator
    async def _setup(self, resolved_deps):
        __tracebackhide__ = True
        gen = self.fixturedef.func(**resolved_deps)

        try:
            await yield_(gen.send(None))
        finally:
            try:
                gen.send(None)
            except StopIteration:
                pass
            else:
                raise RuntimeError('Only one yield in fixture is allowed')


class AsyncFixture(BaseAsyncFixture):
    """
    Regular async fixture (i.e. coroutine).
    """

    @asynccontextmanager
    @async_generator
    async def _setup(self, resolved_deps):
        __tracebackhide__ = True
        await yield_(await self.fixturedef.func(**resolved_deps))


def _install_async_fixture_if_needed(fixturedef, request):
    asyncfix = None
    deps = {dep: request.getfixturevalue(dep) for dep in fixturedef.argnames}
    if iscoroutinefunction(fixturedef.func):
        asyncfix = AsyncFixture(fixturedef, deps)
    elif isasyncgenfunction(fixturedef.func):
        asyncfix = AsyncYieldFixture(fixturedef, deps)
    elif any(isinstance(dep, BaseAsyncFixture) for dep in deps.values()):
        if isgeneratorfunction(fixturedef.func):
            asyncfix = SyncYieldFixtureWithAsyncDeps(fixturedef, deps)
        else:
            asyncfix = SyncFixtureWithAsyncDeps(fixturedef, deps)
    if asyncfix:
        fixturedef.cached_result = (asyncfix, request.param_index, None)
        return asyncfix


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    if 'trio' in item.keywords:
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


@pytest.hookimpl()
def pytest_fixture_setup(fixturedef, request):
    if 'trio' in request.keywords:
        return _install_async_fixture_if_needed(fixturedef, request)


################################################################
# Built-in fixtures
################################################################


@pytest.fixture
def mock_clock():
    return MockClock()


@pytest.fixture
def autojump_clock():
    return MockClock(autojump_threshold=0)


@pytest.fixture
async def nursery(request):
    return request.node._trio_nursery
