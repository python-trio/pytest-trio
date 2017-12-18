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
from trio.testing import MockClock, trio_test


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
        resolved_kwargs = await _setup_async_fixtures_in(kwargs)
        await testfunc(**resolved_kwargs)
        await _teardown_async_fixtures_in(kwargs)

    return _bootstrap_fixture_and_run_test


async def _setup_async_fixtures_in(deps):
    resolved_deps = {**deps}

    for depname, depval in resolved_deps.items():
        if isinstance(depval, BaseAsyncFixture):
            resolved_deps[depname] = await depval.setup()

    return resolved_deps


async def _teardown_async_fixtures_in(deps):
    for depval in deps.values():
        if isinstance(depval, BaseAsyncFixture):
            await depval.teardown()


class BaseAsyncFixture:
    """
    Represent a fixture that need to be run in a trio context to be resolved.
    """

    def __init__(self, fixturedef, deps={}):
        self.fixturedef = fixturedef
        self.deps = deps
        self.setup_done = False
        self.teardown_done = False
        self.result = None
        self.lock = trio.Lock()

    async def setup(self):
        async with self.lock:
            if not self.setup_done:
                self.result = await self._setup()
                self.setup_done = True
            return self.result

    async def _setup(self):
        raise NotImplementedError()

    async def teardown(self):
        async with self.lock:
            if not self.teardown_done:
                await self._teardown()
                self.teardown_done = True

    async def _teardown(self):
        raise NotImplementedError()


class AsyncYieldFixture(BaseAsyncFixture):
    """
    Async generator fixture.
    """

    def __init__(self, *args):
        super().__init__(*args)
        self.agen = None

    async def _setup(self):
        resolved_deps = await _setup_async_fixtures_in(self.deps)
        self.agen = self.fixturedef.func(**resolved_deps)
        return await self.agen.asend(None)

    async def _teardown(self):
        try:
            await self.agen.asend(None)
        except StopAsyncIteration:
            await _teardown_async_fixtures_in(self.deps)
        else:
            raise RuntimeError('Only one yield in fixture is allowed')


class SyncFixtureWithAsyncDeps(BaseAsyncFixture):
    """
    Synchronous function fixture with asynchronous dependencies fixtures.
    """

    async def _setup(self):
        resolved_deps = await _setup_async_fixtures_in(self.deps)
        return self.fixturedef.func(**resolved_deps)

    async def _teardown(self):
        await _teardown_async_fixtures_in(self.deps)


class SyncYieldFixtureWithAsyncDeps(BaseAsyncFixture):
    """
    Synchronous generator fixture with asynchronous dependencies fixtures.
    """

    def __init__(self, *args):
        super().__init__(*args)
        self.agen = None

    async def _setup(self):
        resolved_deps = await _setup_async_fixtures_in(self.deps)
        self.gen = self.fixturedef.func(**resolved_deps)
        return self.gen.send(None)

    async def _teardown(self):
        try:
            await self.gen.send(None)
        except StopIteration:
            await _teardown_async_fixtures_in(self.deps)
        else:
            raise RuntimeError('Only one yield in fixture is allowed')


class AsyncFixture(BaseAsyncFixture):
    """
    Regular async fixture (i.e. coroutine).
    """

    async def _setup(self):
        resolved_deps = await _setup_async_fixtures_in(self.deps)
        return await self.fixturedef.func(**resolved_deps)

    async def _teardown(self):
        await _teardown_async_fixtures_in(self.deps)


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
