Quickstart
==========

Enabling Trio mode and running your first async tests
-----------------------------------------------------

.. note:: If you used `cookiecutter-trio
   <https://github.com/python-trio/cookiecutter-trio>`__ to set up
   your project, then pytest-trio and Trio mode are already
   configured! You can write ``async def test_whatever(): ...`` and it
   should just work. Feel free to skip to the next section.

Let's make a temporary directory to work in, and write two trivial
tests: one that we expect should pass, and one that we expect should
fail::

   # test_example.py
   import trio

   async def test_sleep():
       start_time = trio.current_time()
       await trio.sleep(1)
       end_time = trio.current_time()
       assert end_time - start_time >= 1

   async def test_should_fail():
       assert False

If we run this under pytest normally, then the tests are skipped and we get
a warning explaining how pytest itself does not directly support async def
tests.  Note that in versions of pytest prior to v4.4.0 the tests end up
being reported as passing with other warnings despite not actually having
been properly run.

.. code-block:: none

   $ pytest test_example.py
   ======================== test session starts =========================
   platform linux -- Python 3.8.5, pytest-6.0.1, py-1.9.0, pluggy-0.13.1
   rootdir: /tmp
   collected 2 items

   test_example.py ss                                             [100%]

   ========================== warnings summary ==========================
   test_example.py::test_sleep
   test_example.py::test_should_fail
     .../_pytest/python.py:169: PytestUnhandledCoroutineWarning: async
     def functions are not natively supported and have been skipped.
     You need to install a suitable plugin for your async framework, for
     example:
       - pytest-asyncio
       - pytest-trio
       - pytest-tornasync
       - pytest-twisted
       warnings.warn(PytestUnhandledCoroutineWarning(msg.format(nodeid)))

   -- Docs: https://docs.pytest.org/en/stable/warnings.html
   =================== 2 skipped, 2 warnings in 0.26s ===================

Here's the fix:

1. Install pytest-trio: ``pip install pytest-trio``

2. In your project root, create a file called ``pytest.ini`` with
   contents:

   .. code-block:: none

      [pytest]
      trio_mode = true

And we're done! Let's try running pytest again:

.. code-block:: none

   $ pip install pytest-trio

   $ cat <<EOF >pytest.ini
   [pytest]
   trio_mode = true
   EOF

   $ pytest test_example.py
   ======================== test session starts =========================
   platform linux -- Python 3.8.5, pytest-6.0.1, py-1.9.0, pluggy-0.13.1
   rootdir: /tmp, configfile: pytest.ini
   plugins: trio-0.6.0
   collected 2 items

   test_example.py .F                                             [100%]

   ============================== FAILURES ==============================
   __________________________ test_should_fail __________________________

   value = <trio.Nursery object at 0x7f97b21fafa0>

       async def yield_(value=None):
   >       return await _yield_(value)

   venv/lib/python3.8/site-packages/async_generator/_impl.py:106:
   _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
   venv/lib/python3.8/site-packages/async_generator/_impl.py:99: in _yield_
       return (yield _wrap(value))
   _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

       async def test_should_fail():
   >       assert False
   E       assert False

   test_example.py:11: AssertionError
   ====================== short test summary info =======================
   FAILED test_example.py::test_should_fail - assert False
   ==================== 1 failed, 1 passed in 1.23s =====================

Notice that now it says ``plugins: trio``, which means that
pytest-trio is installed, and the results make sense: the good test
passed, the bad test failed, no warnings, and it took just over 1
second, like we'd expect.


Trio's magic autojump clock
---------------------------

Tests involving time are often slow and flaky. But we can
fix that. Just add the ``autojump_clock`` fixture to your test, and
it will run in a mode where Trio's clock is virtualized and
deterministic. Essentially, the clock doesn't move, except that whenever all
tasks are blocked waiting, it jumps forward until the next time when
something will happen::

   # Notice the 'autojump_clock' argument: that's all it takes!
   async def test_sleep_efficiently_and_reliably(autojump_clock):
       start_time = trio.current_time()
       await trio.sleep(1)
       end_time = trio.current_time()
       assert start_time - end_time == 1

In the version of this test we saw before that used real time, at the
end we had to use a ``>=`` comparison, in order to account for
scheduler jitter and so forth. If there were a bug that caused
:func:`trio.sleep` to take 10 seconds, our test wouldn't have noticed.
But now we're using virtual time, so the call to ``await
trio.sleep(1)`` takes *exactly* 1 virtual second, and the ``==`` test
will pass every time. Before, we had to wait around for the test to
complete; now, it completes essentially instantaneously. (Try it!)
And, while here our example is super simple, its integration with
Trio's core scheduling logic allows this to work for arbitrarily
complex programs (as long as they aren't interacting with the outside
world).


Async fixtures
--------------

We can write async fixtures::

   @pytest.fixture
   async def db_connection():
       return await some_async_db_library.connect(...)

   async def test_example(db_connection):
       await db_connection.execute("SELECT * FROM ...")

If you need to run teardown code, you can use ``yield``, just like a
regular pytest fixture::

   # DB connection that wraps each test in a transaction and rolls it
   # back afterwards
   @pytest.fixture
   async def rollback_db_connection():
       # Setup code
       connection = await some_async_db_library.connect(...)
       await connection.execute("START TRANSACTION")

       # The value of this fixture
       yield connection

       # Teardown code, executed after the test is done
       await connection.execute("ROLLBACK")

If you need to support Python 3.5, which doesn't allow ``yield``
inside an ``async def`` function, then you can define async fixtures
using the `async_generator
<https://async-generator.readthedocs.io/en/latest/reference.html>`__
library – just make sure to put the ``@pytest.fixture`` *above* the
``@async_generator``.


.. _server-fixture-example:

Running a background server from a fixture
------------------------------------------

Here's some code to implement an echo server. It's supposed to take in
arbitrary data, and then send it back out again::

   async def echo_server_handler(stream):
       while True:
           data = await stream.receive_some(1000)
           if not data:
               break
           await stream.send_all(data)

   # Usage: await trio.serve_tcp(echo_server_handler, ...)

Now we need to test it, to make sure it's working correctly. In fact,
since this is such complicated and sophisticated code, we're going to
write lots of tests for it. And they'll all follow the same basic
pattern: we'll start the echo server running in a background task,
then connect to it, send it some test data, and see how it responds.
Here's a first attempt::

   # Let's cross our fingers and hope no-one else is using this port...
   PORT = 14923

   # Don't copy this -- we can do better
   async def test_attempt_1():
       async with trio.open_nursery() as nursery:
           # Start server running in the background
           nursery.start_soon(
               partial(trio.serve_tcp, echo_server_handler, port=PORT)
           )

           # Connect to the server.
           echo_client = await trio.open_tcp_stream("127.0.0.1", PORT)
           # Send some test data, and check that it gets echoed back
           async with echo_client:
               for test_byte in [b"a", b"b", b"c"]:
                   await echo_client.send_all(test_byte)
                   assert await echo_client.receive_some(1) == test_byte

This will mostly work, but it has a few problems. The most obvious one
is that when we run it, even if everything works perfectly, it will
hang at the end of the test – we never shut down the server, so the
nursery block will wait forever for it to exit.

To avoid this, we should cancel the nursery at the end of the test:

.. code-block:: python3
   :emphasize-lines: 7,20,21

   # Let's cross our fingers and hope no-one else is using this port...
   PORT = 14923

   # Don't copy this -- we can do better
   async def test_attempt_2():
       async with trio.open_nursery() as nursery:
           try:
               # Start server running in the background
               nursery.start_soon(
                   partial(trio.serve_tcp, echo_server_handler, port=PORT)
               )

               # Connect to the server.
               echo_client = await trio.open_tcp_stream("127.0.0.1", PORT)
               # Send some test data, and check that it gets echoed back
               async with echo_client:
                   for test_byte in [b"a", b"b", b"c"]:
                       await echo_client.send_all(test_byte)
                       assert await echo_client.receive_some(1) == test_byte
           finally:
               nursery.cancel_scope.cancel()

In fact, this pattern is *so* common, that pytest-trio provides a
handy :data:`nursery` fixture to let you skip the boilerplate. Just
add ``nursery`` to your test function arguments, and pytest-trio will
open a nursery, pass it in to your function, and then cancel it for
you afterwards:

.. code-block:: python3
   :emphasize-lines: 5

   # Let's cross our fingers and hope no-one else is using this port...
   PORT = 14923

   # Don't copy this -- we can do better
   async def test_attempt_3(nursery):
       # Start server running in the background
       nursery.start_soon(
           partial(trio.serve_tcp, echo_server_handler, port=PORT)
       )

       # Connect to the server.
       echo_client = await trio.open_tcp_stream("127.0.0.1", PORT)
       # Send some test data, and check that it gets echoed back
       async with echo_client:
           for test_byte in [b"a", b"b", b"c"]:
               await echo_client.send_all(test_byte)
               assert await echo_client.receive_some(1) == test_byte

Next problem: we have a race condition. We spawn a background task to
call ``serve_tcp``, and then immediately try to connect to that
server. Sometimes this will work fine. But it takes a little while for
the server to start up and be ready to accept connections – so other
times, randomly, our connection attempt will happen too quickly, and
error out. After all – ``nursery.start_soon`` only promises that the
task will be started *soon*, not that it has actually happened. So this
test will be flaky, and flaky tests are the worst.

Fortunately, Trio makes this easy to solve, by switching to using
``await nursery.start(...)``. You can `read its docs for full details
<https://trio.readthedocs.io/en/latest/reference-core.html#trio.The%20nursery%20interface.start>`__,
but basically the idea is that both ``nursery.start_soon(...)`` and
``await nursery.start(...)`` create background tasks, but only
``start`` waits for the new task to finish getting itself set up. This
requires some cooperation from the background task: it has to notify
``nursery.start`` when it's ready. Fortunately, :func:`trio.serve_tcp`
already knows how to cooperate with ``nursery.start``, so we can
write:

.. code-block:: python3
   :emphasize-lines: 6-10

   # Let's cross our fingers and hope no-one else is using this port...
   PORT = 14923

   # Don't copy this -- we can do better
   async def test_attempt_4(nursery):
       # Start server running in the background
       # AND wait for it to finish starting up before continuing
       await nursery.start(
           partial(trio.serve_tcp, echo_server_handler, port=PORT)
       )

       # Connect to the server
       echo_client = await trio.open_tcp_stream("127.0.0.1", PORT)
       async with echo_client:
           for test_byte in [b"a", b"b", b"c"]:
               await echo_client.send_all(test_byte)
               assert await echo_client.receive_some(1) == test_byte

That solves our race condition. Next issue: hardcoding the port number
like this is a bad idea, because port numbers are a machine-wide
resource, so if we're unlucky some other program might already be
using it. What we really want to do is to tell :func:`~trio.serve_tcp`
to pick a random port that no-one else is using. It turns out that
this is easy: if you request port 0, then the operating system will
pick an unused one for you automatically. Problem solved!

But wait... if the operating system is picking the port for us, how do
we know which one it picked, so we can connect to it later?

Well, there's no way to predict the port ahead of time. But after
:func:`~trio.serve_tcp` has opened a port, it can check and see what
it got. So we need some way to pass this data back out of
:func:`~trio.serve_tcp`. Fortunately, ``nursery.start`` handles this
too: it lets the task pass out a piece of data after it has started. And
it just so happens that what :func:`~trio.serve_tcp` passes out is a
list of :class:`~trio.SocketListener` objects. And there's a handy
function called :func:`trio.testing.open_stream_to_socket_listener`
that can take a :class:`~trio.SocketListener` and make a connection to
it.

Putting it all together:

.. code-block:: python3
   :emphasize-lines: 1,8,13-16

   from trio.testing import open_stream_to_socket_listener

   # Don't copy this -- it finally works, but we can still do better!
   async def test_attempt_5(nursery):
       # Start server running in the background
       # AND wait for it to finish starting up before continuing
       # AND find out where it's actually listening
       listeners = await nursery.start(
           partial(trio.serve_tcp, echo_server_handler, port=0)
       )

       # Connect to the server.
       # There might be multiple listeners (example: IPv4 and
       # IPv6), but we don't care which one we connect to, so we
       # just use the first.
       echo_client = await open_stream_to_socket_listener(listeners[0])
       async with echo_client:
           for test_byte in [b"a", b"b", b"c"]:
               await echo_client.send_all(test_byte)
               assert await echo_client.receive_some(1) == test_byte

Now, this works – but there's still a lot of boilerplate. Remember, we
need to write lots of tests for this server, and we don't want to have
to copy-paste all that stuff into every test. Let's factor out the
setup into a fixture::

   @pytest.fixture
   async def echo_client(nursery):
       listeners = await nursery.start(
           partial(trio.serve_tcp, echo_server_handler, port=0)
       )
       echo_client = await open_stream_to_socket_listener(listeners[0])
       async with echo_client:
           yield echo_client

And now in tests, all we have to do is request the ``echo_client``
fixture, and we get a background server and a client stream connected
to it. So here's our complete, final version::

   # Final version -- copy this!
   from functools import partial
   import pytest
   import trio
   from trio.testing import open_stream_to_socket_listener

   # The code being tested:
   async def echo_server_handler(stream):
       while True:
           data = await stream.receive_some(1000)
           if not data:
               break
           await stream.send_all(data)

   # The fixture:
   @pytest.fixture
   async def echo_client(nursery):
       listeners = await nursery.start(
           partial(trio.serve_tcp, echo_server_handler, port=0)
       )
       echo_client = await open_stream_to_socket_listener(listeners[0])
       async with echo_client:
           yield echo_client

   # A test using the fixture:
   async def test_final(echo_client):
       for test_byte in [b"a", b"b", b"c"]:
           await echo_client.send_all(test_byte)
           assert await echo_client.receive_some(1) == test_byte

No hangs, no race conditions, simple, clean, and reusable.
