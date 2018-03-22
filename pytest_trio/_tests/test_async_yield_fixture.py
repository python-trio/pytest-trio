import sys
import pytest


@pytest.mark.skipif(sys.version_info < (3, 6), reason="requires python3.6")
def test_single_async_yield_fixture(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio

        events = []

        @pytest.fixture
        async def fix1():
            events.append('fix1 setup')
            await trio.sleep(0)

            yield 'fix1'

            await trio.sleep(0)
            events.append('fix1 teardown')

        def test_before():
            assert not events

        @pytest.mark.trio
        async def test_actual_test(fix1):
            assert events == ['fix1 setup']
            assert fix1 == 'fix1'

        def test_after():
            assert events == [
                'fix1 setup',
                'fix1 teardown',
            ]
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=3)


@pytest.mark.skipif(sys.version_info < (3, 6), reason="requires python3.6")
def test_nested_async_yield_fixture(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio

        events = []

        @pytest.fixture
        async def fix2():
            events.append('fix2 setup')
            await trio.sleep(0)

            yield 'fix2'

            await trio.sleep(0)
            events.append('fix2 teardown')

        @pytest.fixture
        async def fix1(fix2):
            events.append('fix1 setup')
            await trio.sleep(0)

            yield 'fix1'

            await trio.sleep(0)
            events.append('fix1 teardown')

        def test_before():
            assert not events

        @pytest.mark.trio
        async def test_actual_test(fix1):
            assert events == [
                'fix2 setup',
                'fix1 setup',
            ]
            assert fix1 == 'fix1'

        def test_after():
            assert events == [
                'fix2 setup',
                'fix1 setup',
                'fix1 teardown',
                'fix2 teardown',
            ]
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=3)


@pytest.mark.skipif(sys.version_info < (3, 6), reason="requires python3.6")
def test_async_yield_fixture_within_sync_fixture(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio

        events = []

        @pytest.fixture
        async def fix2():
            events.append('fix2 setup')
            await trio.sleep(0)

            yield 'fix2'

            await trio.sleep(0)
            events.append('fix2 teardown')

        @pytest.fixture
        def fix1(fix2):
            return 'fix1'

        def test_before():
            assert not events

        @pytest.mark.trio
        async def test_actual_test(fix1):
            assert events == [
                'fix2 setup',
            ]
            assert fix1 == 'fix1'

        def test_after():
            assert events == [
                'fix2 setup',
                'fix2 teardown',
            ]
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=3)


@pytest.mark.skipif(sys.version_info < (3, 6), reason="requires python3.6")
def test_async_yield_fixture_within_sync_yield_fixture(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio

        events = []

        @pytest.fixture
        async def fix2():
            events.append('fix2 setup')
            await trio.sleep(0)

            yield 'fix2'

            await trio.sleep(0)
            events.append('fix2 teardown')

        @pytest.fixture
        def fix1(fix2):
            events.append('fix1 setup')
            yield 'fix1'
            events.append('fix1 teardown')

        def test_before():
            assert not events

        @pytest.mark.trio
        async def test_actual_test(fix1):
            assert events == [
                'fix2 setup',
                'fix1 setup',
            ]
            assert fix1 == 'fix1'

        def test_after():
            assert events == [
                'fix2 setup',
                'fix1 setup',
                'fix1 teardown',
                'fix2 teardown',
            ]
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=3)


@pytest.mark.skipif(sys.version_info < (3, 6), reason="requires python3.6")
def test_async_yield_fixture_with_multiple_yields(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio

        @pytest.fixture
        async def fix1():
            await trio.sleep(0)
            yield 'good'
            await trio.sleep(0)
            yield 'bad'

        @pytest.mark.trio
        async def test_actual_test(fix1):
            pass
    """
    )

    result = testdir.runpytest()

    # TODO: should trigger error instead of failure
    # result.assert_outcomes(error=1)
    result.assert_outcomes(failed=1)


@pytest.mark.skipif(sys.version_info < (3, 6), reason="requires python3.6")
def test_async_yield_fixture_with_nursery(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio


        async def handle_client(stream):
            while True:
                buff = await stream.receive_some(4)
                await stream.send_all(buff)


        @pytest.fixture
        async def server():
            async with trio.open_nursery() as nursery:
                listeners = await nursery.start(trio.serve_tcp, handle_client, 0)
                yield listeners[0]
                nursery.cancel_scope.cancel()


        @pytest.mark.trio
        async def test_actual_test(server):
            stream = await trio.testing.open_stream_to_socket_listener(server)
            await stream.send_all(b'ping')
            rep = await stream.receive_some(4)
            assert rep == b'ping'
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=1)


@pytest.mark.skipif(sys.version_info < (3, 6), reason="requires python3.6")
def test_async_yield_fixture_crashed_teardown_allow_other_teardowns(testdir):

    testdir.makepyfile(
        """
        import pytest
        import trio

        events = []

        @pytest.fixture
        async def good_fixture():
            async with trio.open_nursery() as nursery:
                events.append('good_fixture setup')
                yield
                events.append('good_fixture teardown')

        @pytest.fixture
        async def bad_fixture():
            async with trio.open_nursery() as nursery:
                events.append('bad_fixture setup')
                yield
                events.append('bad_fixture teardown')
                raise RuntimeError('Crash during fixture teardown')
                # Cannot cancel offtask's scope

        def test_before():
            assert not events

        @pytest.mark.trio
        async def test_actual_test(bad_fixture, good_fixture):
            pass

        def test_after():
            assert events == [
                'good_fixture setup',
                'bad_fixture setup',
                'bad_fixture teardown',
            ]
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(failed=1, passed=2)
    result.stdout.re_match_lines('E       RuntimeError: Crash during fixture teardown')
