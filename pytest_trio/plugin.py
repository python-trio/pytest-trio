"""pytest-trio implementation."""
import sys
from traceback import format_exception
from collections.abc import Coroutine, Generator
from inspect import iscoroutinefunction, isgeneratorfunction
import contextvars
import outcome
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

try:
    from hypothesis import register_random
except ImportError:  # pragma: no cover
    pass
else:
    # On recent versions of Hypothesis, make the Trio scheduler deterministic
    # even though it uses a module-scoped Random instance.  This works
    # regardless of whether or not the random_module strategy is used.
    register_random(trio._core._run._r)
    # We also have to enable determinism, which is disabled by default
    # due to a small performance impact - but fine to enable in testing.
    # See https://github.com/python-trio/trio/pull/890/ for details.
    trio._core._run._ALLOW_DETERMINISTIC_SCHEDULING = True


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
# Core support for trio fixtures and trio tests
################################################################

# This is more complicated than you might expect.

# The first complication is that all of pytest's machinery for setting up,
# running a test, and then tearing it down again is synchronous. But we want
# to have async setup, async tests, and async teardown.
#
# Our trick: from pytest's point of view, trio fixtures return an unevaluated
# placeholder value, a TrioFixture object. This contains all the information
# needed to do the actual setup/teardown, but doesn't actually perform these
# operations.
#
# Then, pytest runs what it thinks of as "the test", we enter trio, and use
# our own logic to setup the trio fixtures, run the actual test, and then tear
# down the trio fixtures. This works pretty well, though it has some
# limitations:
# - trio fixtures have to be test-scoped
# - normally pytest considers a fixture crash to be an ERROR, but when a trio
#   fixture crashes, it gets classified as a FAIL.

# The other major complication is that we really want to allow trio fixtures
# to yield inside a nursery. (See gh-55 for more discussion.) And then while
# the fixture function is suspended, a task inside that nursery might crash.
#
# Why is this a problem? Two reasons. First, a technical one: Trio's cancel
# scope machinery assumes that it can inject a Cancelled exception into any
# code inside the cancel scope, and that exception will eventually make its
# way back to the 'with' block.
#
# A fixture that yields inside a nursery violates this rule: the cancel scope
# remains "active" from when the fixture yields until when it's reentered, but
# if a Cancelled exception is raised during this time, then it *won't* go into
# the fixture. (And we can't throw it in there either, because that's just not
# how pytest fixtures work. Whoops.)
#
# And second, our setup/test/teardown process needs to account for the
# possibility that any fixture's background task might crash at any moment,
# and do something sensible with it.
#
# You should think of fixtures as a dependency graph: each fixtures *uses*
# zero or more other fixtures, and is *used by* zero or more other fixtures.
# A fixture should be setup before any of its dependees are setup, and torn
# down once all of its dependees have terminated.
# At the root of this dependency graph, we have the test itself,
# which is just like a fixture except that instead of having a separate setup
# and teardown phase, it runs straight through.
#
# To implement this, we isolate each fixture into its own task: this makes
# sure that crashes in one can't trigger implicit cancellation in another.
# Then we use trio.Event objects to implement the ordering described above.
#
# If a fixture crashes, whether during setup, teardown, or in a background
# task at any other point, then we mark the whole test run as "crashed". When
# a run is "crashed", two things happen: (1) if any fixtures or the test
# itself haven't started yet, then we don't start them. (2) if the test is
# running, we cancel it. That's all. In particular, if a fixture has a
# background crash, we don't propagate that to any other fixtures, we still
# follow the normal teardown sequence, and so on – but since the test is
# cancelled, the teardown sequence should start immediately.

canary = contextvars.ContextVar("pytest-trio canary")


class TrioTestContext:
    def __init__(self):
        self.crashed = False
        self.test_cancel_scope = None
        self.fixtures_with_errors = set()
        self.fixtures_with_cancel = set()
        self.error_list = []

    def crash(self, fixture, exc):
        if exc is None:
            self.fixtures_with_cancel.add(fixture)
        else:
            self.error_list.append(exc)
            self.fixtures_with_errors.add(fixture)
        self.crashed = True
        if self.test_cancel_scope is not None:
            self.test_cancel_scope.cancel()


class TrioFixture:
    """
    Represent a fixture that need to be run in a trio context to be resolved.

    The name is actually a misnomer, because we use it to represent the actual
    test itself as well, since the test is basically just a fixture with no
    dependents and no teardown.
    """

    def __init__(self, name, func, pytest_kwargs, is_test=False):
        self.name = name
        self._func = func
        self._pytest_kwargs = pytest_kwargs
        self._is_test = is_test
        self._teardown_done = trio.Event()

        # These attrs are all accessed from other objects:
        # Downstream users read this value.
        self.fixture_value = None
        # This event notifies downstream users that we're done setting up.
        # Invariant: if this is set, then either fixture_value is usable *or*
        # test_ctx.crashed is True.
        self.setup_done = trio.Event()
        # Downstream users *modify* this value, by adding their _teardown_done
        # events to it, so we know who we need to wait for before tearing
        # down.
        self.user_done_events = set()

    def register_and_collect_dependencies(self):
        # Returns the set of all TrioFixtures that this fixture depends on,
        # directly or indirectly, and sets up all their user_done_events.
        deps = set()
        deps.add(self)
        for value in self._pytest_kwargs.values():
            if isinstance(value, TrioFixture):
                value.user_done_events.add(self._teardown_done)
                deps.update(value.register_and_collect_dependencies())
        return deps

    @asynccontextmanager
    @async_generator
    async def _fixture_manager(self, test_ctx):
        __tracebackhide__ = True
        try:
            async with trio.open_nursery() as nursery_fixture:
                try:
                    await yield_(nursery_fixture)
                finally:
                    nursery_fixture.cancel_scope.cancel()
        except BaseException as exc:
            test_ctx.crash(self, exc)
        finally:
            self.setup_done.set()
            self._teardown_done.set()

    async def run(self, test_ctx, contextvars_ctx):
        __tracebackhide__ = True

        # This is a gross hack. I guess Trio should provide a context=
        # argument to start_soon/start?
        task = trio.lowlevel.current_task()
        assert canary not in task.context
        task.context = contextvars_ctx
        # Force a yield so we pick up the new context
        await trio.sleep(0)
        # Check that it worked, since technically trio doesn't *guarantee*
        # that sleep(0) will actually yield.
        assert canary.get() == "in correct context"

        # This 'with' block handles the nursery fixture lifetime, the
        # teardone_done event, and crashing the context if there's an
        # unhandled exception.
        async with self._fixture_manager(test_ctx) as nursery_fixture:
            # Resolve our kwargs
            resolved_kwargs = {}
            for name, value in self._pytest_kwargs.items():
                if isinstance(value, TrioFixture):
                    await value.setup_done.wait()
                    if value.fixture_value is NURSERY_FIXTURE_PLACEHOLDER:
                        resolved_kwargs[name] = nursery_fixture
                    else:
                        resolved_kwargs[name] = value.fixture_value
                else:
                    resolved_kwargs[name] = value

            # If something's already crashed before we're ready to start, then
            # there's no point in even setting up.
            if test_ctx.crashed:
                return

            # Run actual fixture setup step
            if self._is_test:
                # Tests are exactly like fixtures, except that they (1) have
                # to be regular async functions, (2) if there's a crash, we
                # should cancel them.
                assert not self.user_done_events
                func_value = None
                with trio.CancelScope() as cancel_scope:
                    test_ctx.test_cancel_scope = cancel_scope
                    assert not test_ctx.crashed
                    await self._func(**resolved_kwargs)
            else:
                func_value = self._func(**resolved_kwargs)
                if isinstance(func_value, Coroutine):
                    self.fixture_value = await func_value
                elif isasyncgen(func_value):
                    self.fixture_value = await func_value.asend(None)
                elif isinstance(func_value, Generator):
                    self.fixture_value = func_value.send(None)
                else:
                    # Regular synchronous function
                    self.fixture_value = func_value

            # Notify our users that self.fixture_value is ready
            self.setup_done.set()

            # Wait for users to be finished
            #
            # At this point we're in a very strange state: if the fixture
            # yielded inside a nursery or cancel scope, then we are still
            # "inside" that scope even though its with block is not on the
            # stack. In particular this means that if they get cancelled, then
            # our waiting might get a Cancelled error, that we cannot really
            # deal with – it should get thrown back into the fixture
            # generator, but pytest fixture generators don't work that way:
            #   https://github.com/python-trio/pytest-trio/issues/55
            # And besides, we can't start tearing down until all our users
            # have finished.
            #
            # So if we get an exception here, we crash the context (which
            # cancels the test and starts the cleanup process), save any
            # exception that *isn't* Cancelled (because if its Cancelled then
            # we can't route it to the right place, and anyway the teardown
            # code will get it again if it matters), and then use a shield to
            # keep waiting for the teardown to finish without having to worry
            # about cancellation.
            yield_outcome = outcome.Value(None)
            try:
                for event in self.user_done_events:
                    await event.wait()
            except BaseException as exc:
                assert isinstance(exc, trio.Cancelled)
                yield_outcome = outcome.Error(exc)
                test_ctx.crash(self, None)
                with trio.CancelScope(shield=True):
                    for event in self.user_done_events:
                        await event.wait()

            # Do our teardown
            if isasyncgen(func_value):
                try:
                    await yield_outcome.asend(func_value)
                except StopAsyncIteration:
                    pass
                else:
                    raise RuntimeError("too many yields in fixture")
            elif isinstance(func_value, Generator):
                try:
                    yield_outcome.send(func_value)
                except StopIteration:
                    pass
                else:
                    raise RuntimeError("too many yields in fixture")


def _trio_test_runner_factory(item, testfunc=None):
    testfunc = testfunc or item.obj

    if getattr(testfunc, '_trio_test_runner_wrapped', False):
        # We have already wrapped this, perhaps because we combined Hypothesis
        # with pytest.mark.parametrize
        return testfunc

    if not iscoroutinefunction(testfunc):
        pytest.fail(
            'test function `%r` is marked trio but is not async' % item
        )

    @trio_test
    async def _bootstrap_fixtures_and_run_test(**kwargs):
        __tracebackhide__ = True

        test_ctx = TrioTestContext()
        test = TrioFixture(
            "<test {!r}>".format(testfunc.__name__),
            testfunc,
            kwargs,
            is_test=True
        )

        contextvars_ctx = contextvars.copy_context()
        contextvars_ctx.run(canary.set, "in correct context")

        async with trio.open_nursery() as nursery:
            for fixture in test.register_and_collect_dependencies():
                nursery.start_soon(
                    fixture.run, test_ctx, contextvars_ctx, name=fixture.name
                )

        silent_cancellers = (
            test_ctx.fixtures_with_cancel - test_ctx.fixtures_with_errors
        )
        if silent_cancellers:
            for fixture in silent_cancellers:
                test_ctx.error_list.append(
                    RuntimeError(
                        "{} cancelled the test but didn't "
                        "raise an error".format(fixture.name)
                    )
                )

        if test_ctx.error_list:
            raise trio.MultiError(test_ctx.error_list)

    _bootstrap_fixtures_and_run_test._trio_test_runner_wrapped = True
    return _bootstrap_fixtures_and_run_test


################################################################
# Hooking up the test/fixture machinery to pytest
################################################################


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    if item.get_closest_marker("trio") is not None:
        if hasattr(item.obj, 'hypothesis'):
            # If it's a Hypothesis test, we go in a layer.
            item.obj.hypothesis.inner_test = _trio_test_runner_factory(
                item, item.obj.hypothesis.inner_test
            )
        elif getattr(item.obj, 'is_hypothesis_test',
                     False):  # pragma: no cover
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


def _is_trio_fixture(func, coerce_async, kwargs):
    if getattr(func, "_force_trio_fixture", False):
        return True
    if (coerce_async and
        (iscoroutinefunction(func) or isasyncgenfunction(func))):
        return True
    if any(isinstance(value, TrioFixture) for value in kwargs.values()):
        return True
    return False


def handle_fixture(fixturedef, request, force_trio_mode):
    is_trio_test = (request.node.get_closest_marker("trio") is not None)
    if force_trio_mode:
        is_trio_mode = True
    else:
        is_trio_mode = request.node.config.getini("trio_mode")
    coerce_async = (is_trio_test or is_trio_mode)
    kwargs = {
        name: request.getfixturevalue(name)
        for name in fixturedef.argnames
    }
    if _is_trio_fixture(fixturedef.func, coerce_async, kwargs):
        if request.scope != "function":
            raise RuntimeError("Trio fixtures must be function-scope")
        if not is_trio_test:
            raise RuntimeError("Trio fixtures can only be used by Trio tests")
        fixture = TrioFixture(
            "<fixture {!r}>".format(fixturedef.argname),
            fixturedef.func,
            kwargs,
        )
        fixturedef.cached_result = (fixture, request.param_index, None)
        return fixture


def pytest_fixture_setup(fixturedef, request):
    return handle_fixture(fixturedef, request, force_trio_mode=False)


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


class NURSERY_FIXTURE_PLACEHOLDER:
    pass


@pytest.fixture
def mock_clock():
    return MockClock()


@pytest.fixture
def autojump_clock():
    return MockClock(autojump_threshold=0)


@trio_fixture
def nursery(request):
    return NURSERY_FIXTURE_PLACEHOLDER
