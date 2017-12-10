"""pytest-trio implementation."""
import contextlib
import inspect
import socket
from functools import partial
from traceback import format_exception

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
        kwargs = await _resolve_async_fixtures_in(kwargs)
        await testfunc(**kwargs)

    return _bootstrap_fixture_and_run_test


async def _resolve_async_fixtures_in(deps):
    resolved_deps = {**deps}

    async def _resolve_and_update_deps(afunc, deps, entry):
        deps[entry] = await afunc()

    async with trio.open_nursery() as nursery:
        for depname, depval in resolved_deps.items():
            if isinstance(depval, AsyncFixture):
                nursery.start_soon(
                    _resolve_and_update_deps, depval.resolve, resolved_deps,
                    depname
                )
    return resolved_deps


class AsyncFixture:
    """
    Represent a fixture that need to be run in a trio context to be resolved.
    Can be async function fixture or a syncronous fixture with async
    dependencies fixtures.
    """
    NOTSET = object()

    def __init__(self, fixturefunc, fixturedef, deps={}):
        self.fixturefunc = fixturefunc
        # Note fixturedef.func
        self.fixturedef = fixturedef
        self.deps = deps
        self._ret = self.NOTSET

    async def resolve(self):
        if self._ret is self.NOTSET:
            resolved_deps = await _resolve_async_fixtures_in(self.deps)
            if inspect.iscoroutinefunction(self.fixturefunc):
                self._ret = await self.fixturefunc(**resolved_deps)
            else:
                self._ret = self.fixturefunc(**resolved_deps)
        return self._ret


def _install_async_fixture_if_needed(fixturedef, request):
    deps = {dep: request.getfixturevalue(dep) for dep in fixturedef.argnames}
    asyncfix = None
    if not deps and inspect.iscoroutinefunction(fixturedef.func):
        # Top level async fixture
        asyncfix = AsyncFixture(fixturedef.func, fixturedef)
    elif any(dep for dep in deps.values() if isinstance(dep, AsyncFixture)):
        # Fixture with async fixture dependencies
        asyncfix = AsyncFixture(fixturedef.func, fixturedef, deps)
    # The async fixture must be evaluated from within the trio context
    # which is spawed in the function test's trio decorator.
    # The trick is to make pytest's fixture call return the AsyncFixture
    # object which will be actully resolved just before we run the test.
    if asyncfix:
        fixturedef.func = lambda **kwargs: asyncfix


@pytest.hookimpl(tryfirst=True)
def pytest_fixture_setup(fixturedef, request):
    if 'trio' in request.keywords:
        _install_async_fixture_if_needed(fixturedef, request)


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(session, config, items):
    # Retrieve test marked as `trio`
    for item in items:
        if 'trio' not in item.keywords:
            continue
        if not inspect.iscoroutinefunction(item.function):
            pytest.fail(
                'test function `%r` is marked trio but is not async' % item
            )
        item.obj = _trio_test_runner_factory(item)


@pytest.hookimpl(tryfirst=True)
def pytest_exception_interact(node, call, report):
    if issubclass(call.excinfo.type, trio.MultiError):
        # TODO: not really elegant (pytest cannot output color with this hack)
        report.longrepr = ''.join(format_exception(*call.excinfo._excinfo))


@pytest.fixture
def unused_tcp_port():
    """Find an unused localhost TCP port from 1024-65535 and return it."""
    with contextlib.closing(socket.socket()) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@pytest.fixture
def unused_tcp_port_factory():
    """A factory function, producing different unused TCP ports."""
    produced = set()

    def factory():
        """Return an unused port."""
        port = unused_tcp_port()

        while port in produced:
            port = unused_tcp_port()

        produced.add(port)

        return port

    return factory


@pytest.fixture
def mock_clock():
    return MockClock()


@pytest.fixture
def autojump_clock():
    return MockClock(autojump_threshold=0)
