"""pytest-trio implementation."""
from traceback import format_exception
from inspect import iscoroutinefunction, isgeneratorfunction
try:
    from inspect import isasyncgenfunction
except ImportError:
    # `inspect.isasyncgenfunction` not available with Python<3.6
    def isasyncgenfunction(x):
        return False


import pytest
import trio
from trio._util import acontextmanager
from trio.testing import MockClock, trio_test
from async_generator import async_generator, yield_


def pytest_configure(config):
    """Inject documentation."""
    config.addinivalue_line(
        "markers", "trio: "
        "mark the test as an async trio test; "
        "it will be run using trio.run"
    )


def _trio_test_runner_factory(item):
    testfunc = item.function

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
                        # exception in there teardown, we mimic this behavior here.
                        user_exc = exc
            except BaseException as exc:
                # If we are here, the exception comes from the fixtures setup
                # or teardown
                if user_exc:
                    raise exc from user_exc
                else:
                    raise exc
            finally:
                # No matter what the nursery fixture should be closed when test is over
                nursery.cancel_scope.cancel()

        # Finally re-raise or original exception coming from the test if needed
        if user_exc:
            raise user_exc

    return _bootstrap_fixture_and_run_test


@acontextmanager
@async_generator
async def _setup_async_fixtures_in(deps):
    __tracebackhide__ = True

    need_resolved_deps_stack = [
        (k, v) for k, v in deps.items() if isinstance(v, BaseAsyncFixture)
    ]

    if not need_resolved_deps_stack:
        await yield_(deps)
        return

    @acontextmanager
    @async_generator
    async def _recursive_setup(deps_stack):
        __tracebackhide__ = True
        name, dep = deps_stack.pop()
        async with dep.setup() as resolved:
            if not deps_stack:
                await yield_([(name, resolved)])
            else:
                async with _recursive_setup(
                    deps_stack
                ) as remains_deps_stack_resolved:
                    await yield_(
                        remains_deps_stack_resolved + [(name, resolved)]
                    )

    async with _recursive_setup(
        need_resolved_deps_stack
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

    @acontextmanager
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

    @acontextmanager
    @async_generator
    async def _setup(self, resolved_deps):
        __tracebackhide__ = True
        agen = self.fixturedef.func(**resolved_deps)

        await yield_(await agen.asend(None))

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

    @acontextmanager
    @async_generator
    async def _setup(self, resolved_deps):
        __tracebackhide__ = True
        await yield_(self.fixturedef.func(**resolved_deps))


class SyncYieldFixtureWithAsyncDeps(BaseAsyncFixture):
    """
    Synchronous generator fixture with asynchronous dependencies fixtures.
    """

    @acontextmanager
    @async_generator
    async def _setup(self, resolved_deps):
        __tracebackhide__ = True
        gen = self.fixturedef.func(**resolved_deps)

        await yield_(gen.send(None))

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

    @acontextmanager
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
    elif any(dep for dep in deps.values()
             if isinstance(dep, BaseAsyncFixture)):
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
        if not iscoroutinefunction(item.obj):
            pytest.fail(
                'test function `%r` is marked trio but is not async' % item
            )
        item.obj = _trio_test_runner_factory(item)

    yield


@pytest.hookimpl()
def pytest_fixture_setup(fixturedef, request):
    if 'trio' in request.keywords:
        return _install_async_fixture_if_needed(fixturedef, request)


@pytest.hookimpl(tryfirst=True)
def pytest_exception_interact(node, call, report):
    if issubclass(call.excinfo.type, trio.MultiError):
        # TODO: not really elegant (pytest cannot output color with this hack)
        report.longrepr = ''.join(format_exception(*call.excinfo._excinfo))


@pytest.fixture
def mock_clock():
    return MockClock()


@pytest.fixture
def autojump_clock():
    return MockClock(autojump_threshold=0)


@pytest.fixture
async def nursery(request):
    return request.node._trio_nursery
