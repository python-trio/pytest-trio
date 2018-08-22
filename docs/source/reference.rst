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
  catch mistakes where a you use an async fixture with a non-async
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

The :mod:`contextvars` module provides a way to create task-local
variables called :class:`~contextvars.ContextVars`. Normally, in Trio,
each task gets its own :class:`~contextvars.Context`. But pytest-trio
overrides this, and for each test it uses a single
:class:`~contextvars.Context` which is shared by all fixtures and the
test function itself.

The benefit of this is that you can set
:class:`~contextvars.ContextVars` inside a fixture, and your settings
will be visible in dependent fixtures and the test itself.

The downside is that if two fixtures are run concurrently (see
previous section), and both mutate the same
:class:`~contextvars.ContextVars`, then there will be a race condition
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
