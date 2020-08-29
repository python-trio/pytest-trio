Reference
=========

Trio mode
---------

Most users will want to enable "Trio mode". Without Trio mode:

* Pytest-trio only handles tests that have been decorated with
  ``@pytest.mark.trio``
* Pytest-trio only handles fixtures if they're async *and* used by a
  test that's decorated with ``@pytest.mark.trio``, or if they're
  decorated with ``@pytest_trio.trio_fixture`` (instead of
  ``@pytest.fixture``).

When Trio mode is enabled, two extra things happen:

* Async tests automatically have the ``trio`` mark added, so you don't
  have to do it yourself.
* Async fixtures using ``@pytest.fixture`` automatically get converted
  to Trio fixtures. (The main effect of this is that it helps you
  catch mistakes like using an async fixture with a non-async
  test.)

There are two ways to enable Trio mode.

The first option is to **use a pytest configuration file**. The exact
rules for how pytest finds configuration files are `a bit complicated
<https://docs.pytest.org/en/latest/customize.html>`__, but you want to
end up with something like:

.. code-block:: ini

   # pytest.ini
   [pytest]
   trio_mode = true

The second option is **use a conftest.py file**. Inside your tests
directory, create a file called ``conftest.py``, with the following
contents::

   # conftest.py
   from pytest_trio.enable_trio_mode import *

This does exactly the same thing as setting ``trio_mode = true`` in
``pytest.ini``, except for two things:

* Some people like to ship their tests as part of their library, so
  they (or their users) can test the final installed software by
  running ``pytest --pyargs PACKAGENAME``. In this mode,
  ``pytest.ini`` files don't work, but ``conftest.py`` files do.

* Enabling Trio mode in ``pytest.ini`` always enables it globally for
  your entire testsuite. Enabling it in ``conftest.py`` only enables
  it for test files that are in the same directory as the
  ``conftest.py``, or its subdirectories.

If you have software that uses multiple async libraries, then you can
use ``conftest.py`` to enable Trio mode for just the part of your
testsuite that uses Trio; or, if you need even finer-grained control,
you can leave Trio mode disabled and use ``@pytest.mark.trio``
explicitly on all your Trio tests.


Trio fixtures
-------------

Normally, pytest runs fixture code before starting the test, and
teardown code afterwards. For technical reasons, we can't wrap this
whole process in :func:`trio.run` – only the test itself. As a
workaround, pytest-trio introduces the concept of a "Trio fixture",
which acts like a normal fixture for most purposes, but actually does
the setup and teardown inside the test's call to :func:`trio.run`.

The following fixtures are treated as Trio fixtures:

* Any function decorated with ``@pytest_trio.trio_fixture``.
* Any async function decorated with ``@pytest.fixture``, *if*
  Trio mode is enabled *or* this fixture is being requested by a Trio
  test.
* Any fixture which depends on a Trio fixture.

The most notable difference between regular fixtures and Trio fixtures
is that regular fixtures can't use Trio APIs, but Trio fixtures can.
Most of the time you don't need to worry about this, because you
normally only call Trio APIs from async functions, and when Trio mode
is enabled, all async fixtures are automatically Trio fixtures.
However, if for some reason you do want to use Trio APIs from a
synchronous fixture, then you'll have to use
``@pytest_trio.trio_fixture``::

   # This fixture is not very useful
   # But it is an example where @pytest.fixture doesn't work
   @pytest_trio.trio_fixture
   def trio_time():
       return trio.current_time()

Only Trio tests can use Trio fixtures. If you have a regular
(synchronous) test that tries to use a Trio fixture, then that's an
error.

And finally, regular fixtures can be `scoped to the test, class,
module, or session
<https://docs.pytest.org/en/latest/fixture.html#scope-sharing-a-fixture-instance-across-tests-in-a-class-module-or-session>`__,
but Trio fixtures **must be test scoped**. Class, module, and session
scope are not supported.


.. _cancel-yield:

An important note about ``yield`` fixtures
------------------------------------------

Like any pytest fixture, Trio fixtures can contain both setup and
teardown code separated by a ``yield``::

   @pytest.fixture
   async def my_fixture():
       ... setup code ...
       yield
       ... teardown code ...

When pytest-trio executes this fixture, it creates a new task, and
runs the setup code until it reaches the ``yield``. Then the fixture's
task goes to sleep. Once the test has finished, the fixture task wakes
up again and resumes at the ``yield``, so it can execute the teardown
code.

So the ``yield`` in a fixture is sort of like calling ``await
wait_for_test_to_finish()``. And in Trio, any ``await``\-able
operation can be cancelled. For example, we could put a timeout on the
``yield``::

   @pytest.fixture
   async def my_fixture():
       ... setup code ...
       with trio.move_on_after(5):
           yield  # this yield gets cancelled after 5 seconds
       ... teardown code ...

Now if the test takes more than 5 seconds to execute, this fixture
will cancel the ``yield``.

That's kind of a strange thing to do, but there's another version of
this that's extremely common. Suppose your fixture spawns a background
task, and then the background task raises an exception. Whenever a
background task raises an exception, it automatically cancels
everything inside the nursery's scope – which includes our ``yield``::

   @pytest.fixture
   async def my_fixture(nursery):
       nursery.start_soon(function_that_raises_exception)
       yield   # this yield gets cancelled after the background task crashes
       ... teardown code ...

If you use fixtures with background tasks, you'll probably end up
cancelling one of these ``yield``\s sooner or later. So what happens
if the ``yield`` gets cancelled?

First, pytest-trio assumes that something has gone wrong and there's
no point in continuing the test. If the top-level test function is
running, then it cancels it.

Then, pytest-trio waits for the test function to finish, and
then begins tearing down fixtures as normal.

During this teardown process, it will eventually reach the fixture
that cancelled its ``yield``. This fixture gets resumed to execute its
teardown logic, but with a special twist: since the ``yield`` was
cancelled, the ``yield`` raises :exc:`trio.Cancelled`.

Now, here's the punchline: this means that in our examples above, the
teardown code might not be executed at all! **This is different from
how pytest fixtures normally work.** Normally, the ``yield`` in a
pytest fixture never raises an exception, so you can be certain that
any code you put after it will execute as normal. But if you have a
fixture with background tasks, and they crash, then your ``yield``
might raise an exception, and Python will skip executing the code
after the ``yield``.

In our experience, most fixtures are fine with this, and it prevents
some `weird problems
<https://github.com/python-trio/pytest-trio/issues/75>`__ that can
happen otherwise. But it's something to be aware of.

If you have a fixture where the ``yield`` might be cancelled but you
still need to run teardown code, then you can use a ``finally``
block::

   @pytest.fixture
   async def my_fixture(nursery):
       nursery.start_soon(function_that_crashes)
       try:
           # This yield could be cancelled...
           yield
       finally:
           # But this code will run anyway
           ... teardown code ...

(But, watch out: the teardown code is still running in a cancelled
context, so if it has any ``await``\s it could raise
:exc:`trio.Cancelled` again.)

Or if you use ``with`` to handle teardown, then you don't have to
worry about this because ``with`` blocks always perform cleanup even
if there's an exception::

   @pytest.fixture
   async def my_fixture(nursery):
       with get_obj_that_must_be_torn_down() as obj:
           nursery.start_soon(function_that_crashes, obj)
           # This could raise trio.Cancelled...
           # ...but that's OK, the 'with' block will still tear down 'obj'
           yield obj


Concurrent setup/teardown
-------------------------

If your test uses multiple fixtures, then for speed, pytest-trio will
try to run their setup and teardown code concurrently whenever this is
possible while respecting the fixture dependencies.

Here's an example, where a test depends on ``fix_b`` and ``fix_c``,
and these both depend on ``fix_a``::

   @trio_fixture
   def fix_a():
       ...

   @trio_fixture
   def fix_b(fix_a):
       ...

   @trio_fixture
   def fix_c(fix_a):
       ...

   @pytest.mark.trio
   async def test_example(fix_b, fix_c):
       ...

When running ``test_example``, pytest-trio will perform the following
sequence of actions:

1. Set up ``fix_a``
2. Set up ``fix_b`` and ``fix_c``, concurrently.
3. Run the test.
4. Tear down ``fix_b`` and ``fix_c``, concurrently.
5. Tear down ``fix_a``.

We're `seeking feedback
<https://github.com/python-trio/pytest-trio/issues/57>`__ on whether
this feature's benefits outweigh its negatives.


Handling of ContextVars
-----------------------

The :mod:`contextvars` module lets you create
:class:`~contextvars.ContextVar` objects to represent task-local
variables. Normally, in Trio, each task gets its own
:class:`~contextvars.Context`, so that changes to
:class:`~contextvars.ContextVar` objects are only visible inside the
task that performs them. But pytest-trio overrides this, and for each
test it uses a single :class:`~contextvars.Context` which is shared by
all fixtures and the test function itself.

The benefit of this is that you can set
:class:`~contextvars.ContextVar` values inside a fixture, and your
settings will be visible in dependent fixtures and the test itself.
For example, `trio-asyncio <https://trio-asyncio.readthedocs.io/>`__
uses a :class:`~contextvars.ContextVar` to hold the current asyncio
loop object, so this lets you open a loop inside a fixture and then
use it inside other fixtures or the test itself.

The downside is that if two fixtures are run concurrently (see
previous section), and both mutate the same
:class:`~contextvars.ContextVar`, then there will be a race condition
and the the final value will be unpredictable. If you make one fixture
depend on the other, then this will force an ordering and make the
final value predictable again.


Built-in fixtures
-----------------

These fixtures are automatically available to any code using
pytest-trio.

.. data:: autojump_clock

   A :class:`trio.testing.MockClock`, configured with ``rate=0,
   autojump_threshold=0``.

.. data:: mock_clock

   A :class:`trio.testing.MockClock`, with its default configuration
   (``rate=0, autojump_threshold=inf``).

What makes these particularly useful is that whenever pytest-trio runs
a test, it checks the fixtures to see if one of them is a
:class:`trio.abc.Clock` object. If so, it passes that object to
:func:`trio.run`. So if your test requests one of these fixtures, it
automatically uses that clock.

If you implement your own :class:`~trio.abc.Clock`, and implement a
fixture that returns it, then it will work the same way.

Of course, like any pytest fixture, you also get the actual object
available. For example, you can call
:meth:`~trio.testing.MockClock.jump`::

   async def test_time_travel(mock_clock):
       assert trio.current_time() == 0
       mock_clock.jump(10)
       assert trio.current_time() == 10

.. data:: nursery

   A nursery created and managed by pytest-trio itself, which
   surrounds the test/fixture that requested it, and is automatically
   cancelled after the test/fixture completes. Basically, these are
   equivalent::

      # Boring way
      async def test_with_background_task():
          async with trio.open_nursery() as nursery:
              try:
                  ...
              finally:
                  nursery.cancel_scope.cancel()

      # Fancy way
      async def test_with_background_task(nursery):
          ...

   For a fixture, the cancellation always happens after the fixture
   completes its teardown phase. (Or if it doesn't have a teardown
   phase, then the cancellation happens after the teardown phase
   *would* have happened.)

   This fixture is even more magical than most pytest fixtures,
   because if it gets requested several times within the same test,
   then it creates multiple nurseries, one for each fixture/test that
   requested it.

   See :ref:`server-fixture-example` for an example of how this can be
   used.


Integration with the Hypothesis library
---------------------------------------

There isn't too much to say here, since the obvious thing just works::

   from hypothesis import given
   import hypothesis.strategies as st

   @given(st.binary())
   async def test_trio_and_hypothesis(data):
       ...

Under the hood, this requires some coordination between Hypothesis and
pytest-trio. Hypothesis runs your test multiple times with different
examples of random data. For each example, pytest-trio calls
:func:`trio.run` again (so you get a fresh clean Trio environment),
sets up any Trio fixtures, runs the actual test, and then tears down
any Trio fixtures. Notice that this is a bit different than regular
pytest fixtures, which are `instantiated once and then re-used for all
<https://github.com/pytest-dev/pytest/issues/916>`__. Most of the time
this shouldn't matter (and `is probably what you want anyway
<https://github.com/HypothesisWorks/hypothesis/issues/377>`__), but in
some unusual cases it could surprise you. And this only applies to
Trio fixtures – if a Trio test uses a mix of regular fixtures and Trio
fixtures, then the regular fixtures will be reused, while the Trio
fixtures will be repeatedly reinstantiated.

Also, pytest-trio only handles ``@given``\-based tests. If you want to
write `stateful tests
<https://hypothesis.readthedocs.io/en/latest/stateful.html>`__ for
Trio-based libraries, then check out `hypothesis-trio
<https://github.com/python-trio/hypothesis-trio>`__.


Using alternative Trio runners
------------------------------

If you are working with a library that provides integration with Trio,
such as via :ref:`guest mode <trio:guest-mode>`, it can be used with
pytest-trio as well.  Setting ``trio_run`` in the pytest configuration
makes your choice the global default for both tests explicitly marked
with ``@pytest.mark.trio`` and those automatically marked by Trio mode.
``trio_run`` presently supports ``trio`` and ``qtrio``.

.. code-block:: ini

   # pytest.ini
   [pytest]
   trio_mode = true
   trio_run = qtrio

.. code-block:: python

   import pytest

   @pytest.mark.trio
   async def test():
       assert True

If you want more granular control or need to use a specific function,
it can be passed directly to the marker.

.. code-block:: python

   import pytest

   @pytest.mark.trio(run=qtrio.run)
   async def test():
       assert True
