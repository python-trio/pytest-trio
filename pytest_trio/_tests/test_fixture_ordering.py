import pytest


def test_fixture_basic_ordering(testdir):
    """
    Tests that:
    - leaf_fix gets set up first and torn down last
    - the two fix_{1,2} fixtures run their setup/teardown code
      in the expected order
      fix_1 setup -> fix_2 setup -> fix_2 teardown -> fix_1 teardown
    """
    testdir.makepyfile(
        """
        import pytest
        from pytest_trio import trio_fixture
        from trio.testing import Sequencer

        setup_events = []
        teardown_events = []

        @trio_fixture
        def seq():
            return Sequencer()

        @pytest.fixture
        async def leaf_fix():
            setup_events.append("leaf_fix setup")
            yield
            teardown_events.append("leaf_fix teardown")

            assert teardown_events == [
                "fix_2 teardown 1",
                "fix_2 teardown 2",
                "fix_1 teardown 1",
                "fix_1 teardown 2",
                "leaf_fix teardown",
            ]

        @pytest.fixture
        async def fix_1(leaf_fix, seq):
            async with seq(0):
                setup_events.append("fix_1 setup 1")
            async with seq(1):
                setup_events.append("fix_1 setup 2")
            yield
            async with seq(6):
                teardown_events.append("fix_1 teardown 1")
            async with seq(7):
                teardown_events.append("fix_1 teardown 2")

        @pytest.fixture
        async def fix_2(leaf_fix, seq):
            async with seq(2):
                setup_events.append("fix_2 setup 1")
            async with seq(3):
                setup_events.append("fix_2 setup 2")
            yield
            async with seq(4):
                teardown_events.append("fix_2 teardown 1")
            async with seq(5):
                teardown_events.append("fix_2 teardown 2")

        @pytest.mark.trio
        async def test_root(fix_1, fix_2):
            assert setup_events == [
                "leaf_fix setup",
                "fix_1 setup 1",
                "fix_1 setup 2",
                "fix_2 setup 1",
                "fix_2 setup 2",
            ]
            assert teardown_events == []

        """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_fixture_complicated_dag_ordering(testdir):
    """
    This test involves several fixtures forming a pretty
    complicated DAG, make sure we got the topological sort in order.
    """
    testdir.makepyfile(
        """
        import pytest
        from pytest_trio import trio_fixture

        setup_events = []
        teardown_events = []

        @trio_fixture
        async def fix_6(fix_7):
            setup_events.append("fix_6 setup")
            yield
            teardown_events.append("fix_6 teardown")

        @pytest.fixture
        async def fix_7():
            setup_events.append("fix_7 setup")
            yield
            teardown_events.append("fix_7 teardown")
            assert teardown_events == [
                "fix_4 teardown",
                "fix_5 teardown",
                "fix_3 teardown",
                "fix_1 teardown",
                "fix_2 teardown",
                "fix_6 teardown",
                "fix_7 teardown",
            ]
        @pytest.fixture
        async def fix_4(fix_5, fix_6, fix_7):
            setup_events.append("fix_4 setup")
            yield
            teardown_events.append("fix_4 teardown")

        @pytest.fixture
        async def fix_5(fix_3):
            setup_events.append("fix_5 setup")
            yield
            teardown_events.append("fix_5 teardown")

        @pytest.fixture
        async def fix_3(fix_1, fix_6):
            setup_events.append("fix_3 setup")
            yield
            teardown_events.append("fix_3 teardown")

        @pytest.fixture
        async def fix_1(fix_2, fix_7):
            setup_events.append("fix_1 setup")
            yield
            teardown_events.append("fix_1 teardown")

        @pytest.fixture
        async def fix_2(fix_6, fix_7):
            setup_events.append("fix_2 setup")
            yield
            teardown_events.append("fix_2 teardown")

        @pytest.mark.trio
        async def test_root(fix_1, fix_2, fix_3, fix_4, fix_5, fix_6, fix_7):
            assert setup_events == [
                "fix_7 setup",
                "fix_6 setup",
                "fix_2 setup",
                "fix_1 setup",
                "fix_3 setup",
                "fix_5 setup",
                "fix_4 setup",
            ]
            assert teardown_events == []
        """
    )
    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_contextvars_modification_follows_fixture_ordering(testdir):
    """
    Tests that fixtures are being set up and tore down synchronously.

    Specifically this ensures that fixtures that modify context variables
    doesn't lead to a race condition.
    This tries to simluate thing like trio_asyncio.open_loop that modifies
    the contextvar.

    Main assertion is that 2 async tasks in teardown (Resource.__aexit__)
    doesn't crash.
    """
    testdir.makepyfile(
        """
        import pytest
        import trio
        from contextlib import asynccontextmanager

        current_value = ContextVar("variable", default=None)

        @asynccontextmanager
        async def variable_setter():
            old_value = current_value.set("value")
            try:
                await trio.sleep(0)
                yield
            finally:
                current_value.reset(old_value)

        class Resource():
            async def __aenter__(self):
                await trio.sleep(0)

            async def __aexit__(self, *_):
                # We need to yield and run another trio task
                await trio.sleep(0)
                assert current_value.get() is not None

        @pytest.fixture
        async def resource():
            async with variable_setter() as loop:
                async with Resource():
                    yield

        @pytest.fixture
        async def trio_asyncio_loop():
            async with variable_setter() as loop:
                yield loop

        @pytest.mark.trio
        async def test_root(trio_asyncio_loop, resource):
            await trio.sleep(0)
            assert True
        """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_nursery_fixture_teardown_ordering(testdir):
    testdir.makepyfile(
        """
        import pytest
        from pytest_trio import trio_fixture
        import trio
        from trio.testing import wait_all_tasks_blocked

        events = []

        async def record_cancel(msg):
            try:
                await trio.sleep_forever()
            finally:
                events.append(msg)

        @pytest.fixture
        def fix0():
            yield
            assert events == [
                "test",
                "test cancel",
                "fix2 teardown",
                "fix2 cancel",
                "fix1 teardown",
                "fix1 cancel",
            ]

        @trio_fixture
        def fix1(nursery):
            nursery.start_soon(record_cancel, "fix1 cancel")
            yield
            events.append("fix1 teardown")

        @trio_fixture
        def fix2(fix1, nursery):
            nursery.start_soon(record_cancel, "fix2 cancel")
            yield
            events.append("fix2 teardown")

        @pytest.mark.trio
        async def test_root(fix2, nursery):
            nursery.start_soon(record_cancel, "test cancel")
            await wait_all_tasks_blocked()
            events.append("test")
        """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_error_message_upon_circular_dependency(testdir):
    """
    Make sure that the error message is produced if there's
    a circular dependency on the fixtures
    """
    testdir.makepyfile(
        """
        import pytest
        from pytest_trio import trio_fixture

        @trio_fixture
        def seq(leaf_fix):
            pass

        @pytest.fixture
        async def leaf_fix(seq):
            pass

        @pytest.mark.trio
        async def test_root(leaf_fix, seq):
            pass
        """
    )

    result = testdir.runpytest()
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(
        ["*recursive dependency involving fixture 'leaf_fix' detected*"]
    )


def test_error_collection(testdir):
    # We want to make sure that pytest ultimately reports all the
    # exceptions. We call .upper() on all the exceptions so that we have
    # tokens to look for in the output corresponding to each exception, where
    # those tokens don't appear at all the source (so we can't get a false
    # positive due to pytest printing out the source file).

    # We sleep at the beginning of all the fixtures to give opportunity
    # for all fixtures to start the setup. Maybe we shouldn't?
    # But for now the sleeps make sure that all the fixtures have
    # started setting up before any of them start crashing.

    # We only expect the crash output of the first fixture that crashes
    # during the setup. This is because the setup are synchronous.
    # Once the fixture has crashed the test contex, the others would
    # immediately return and wouldn't even complete the setup process
    testdir.makepyfile(
        """
        import pytest
        from pytest_trio import trio_fixture
        import trio

        test_started = False

        @trio_fixture
        async def crash_nongen():
            with trio.CancelScope(shield=True):
                await trio.sleep(2)
            raise RuntimeError("crash_nongen".upper())

        @trio_fixture
        async def crash_early_agen():
            with trio.CancelScope(shield=True):
                await trio.sleep(2)
            raise RuntimeError("crash_early_agen".upper())
            yield

        @trio_fixture
        async def crash_late_agen():
            yield
            raise RuntimeError("crash_late_agen".upper())

        async def crash(when, token):
            with trio.CancelScope(shield=True):
                await trio.sleep(when)
                raise RuntimeError(token.upper())

        @trio_fixture
        def crash_background(nursery):
            nursery.start_soon(crash, 1, "crash_background_early")
            nursery.start_soon(crash, 3, "crash_background_late")

        @pytest.mark.trio
        async def test_all_the_crashes(
            autojump_clock,
            crash_nongen, crash_early_agen, crash_late_agen, crash_background,
        ):
            global test_started
            test_started = True

        def test_followup():
            assert not test_started

        """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=1, failed=1)
    result.stdout.fnmatch_lines(["*CRASH_NONGEN*"])


@pytest.mark.parametrize("bgmode", ["nursery fixture", "manual nursery"])
def test_background_crash_cancellation_propagation(bgmode, testdir):
    crashyfix_using_nursery_fixture = """
        @trio_fixture
        def crashyfix(nursery):
            nursery.start_soon(crashy)
            with pytest.raises(trio.Cancelled):
                yield
            # We should be cancelled here
            teardown_deadlines["crashyfix"] = trio.current_effective_deadline()
        """

    crashyfix_using_manual_nursery = """
        @trio_fixture
        async def crashyfix():
            async with trio.open_nursery() as nursery:
                nursery.start_soon(crashy)
                with pytest.raises(trio.Cancelled):
                    yield
                # We should be cancelled here
                teardown_deadlines["crashyfix"] = trio.current_effective_deadline()
        """

    if bgmode == "nursery fixture":
        crashyfix = crashyfix_using_nursery_fixture
    else:
        crashyfix = crashyfix_using_manual_nursery

    testdir.makepyfile(
        """
        import pytest
        from pytest_trio import trio_fixture
        import trio

        teardown_deadlines = {}
        final_time = None

        async def crashy():
            await trio.sleep(1)
            raise RuntimeError

        CRASHYFIX_HERE

        @trio_fixture
        def sidefix():
            yield
            # We should NOT be cancelled here
            teardown_deadlines["sidefix"] = trio.current_effective_deadline()

        @trio_fixture
        def userfix(crashyfix):
            yield
            # Currently we should NOT be cancelled here... though maybe this
            # should change?
            teardown_deadlines["userfix"] = trio.current_effective_deadline()

        @pytest.mark.trio
        async def test_it(userfix, sidefix, autojump_clock):
            try:
                await trio.sleep_forever()
            finally:
                global final_time
                final_time = trio.current_time()


        def test_post():
            assert teardown_deadlines == {
                "crashyfix": -float("inf"),
                "sidefix": float("inf"),
                "userfix": float("inf"),
            }
            assert final_time == 1
        """.replace(
            "CRASHYFIX_HERE", crashyfix
        )
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=1, failed=1)


# See the thread starting at
# https://github.com/python-trio/pytest-trio/pull/77#issuecomment-499979536
# for details on the real case that this was minimized from
def test_complex_cancel_interaction_regression(testdir):
    testdir.makepyfile(
        """
        import pytest
        import trio
        from contextlib import asynccontextmanager

        async def die_soon():
            raise RuntimeError('oops'.upper())

        @asynccontextmanager
        async def async_finalizer():
            try:
                yield
            finally:
                await trio.sleep(0)

        @pytest.fixture
        async def fixture(nursery):
            async with trio.open_nursery() as nursery1:
                async with async_finalizer():
                    async with trio.open_nursery() as nursery2:
                        nursery2.start_soon(die_soon)
                        yield
                        nursery1.cancel_scope.cancel()

        @pytest.mark.trio
        async def test_try(fixture):
            await trio.sleep_forever()
        """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=0, failed=1)
    result.stdout.fnmatch_lines_random(["*OOPS*"])


# Makes sure that
# See https://github.com/python-trio/pytest-trio/issues/120
def test_fixtures_crash_and_hang_concurrently(testdir):
    testdir.makepyfile(
        """
        import trio
        import pytest


        @pytest.fixture
        async def hanging_fixture():
            print("hanging_fixture:start")
            await trio.Event().wait()
            yield
            print("hanging_fixture:end")


        @pytest.fixture
        async def exploding_fixture():
            print("exploding_fixture:start")
            raise Exception
            yield
            print("exploding_fixture:end")


        @pytest.mark.trio
        async def test_fails_right_away(exploding_fixture):
            ...


        @pytest.mark.trio
        async def test_fails_needs_some_scopes(exploding_fixture, hanging_fixture):
            ...
        """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=0, failed=2)
