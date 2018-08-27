.. documentation master file, created by
   sphinx-quickstart on Sat Jan 21 19:11:14 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.


===================================
pytest-trio: Pytest plugin for trio
===================================

This is a pytest plugin to help you test projects that use `Trio
<https://trio.readthedocs.io/>`__, a friendly library for concurrency
and async I/O in Python. Features include:

* Async tests without the boilerplate: just write ``async def
  test_whatever(): ...``.

* Useful fixtures included: use :data:`autojump_clock` for easy
  testing of code with timeouts, or :data:`nursery` to easily set up
  background tasks.

* Write your own async fixtures: set up an async database connection
  or start a server inside a fixture, and then use it in your tests.

* If you have multiple async fixtures, pytest-trio will even do
  setup/teardown concurrently whenever possible. (Though honestly,
  we're not sure whether this is a good idea or not and might remove
  it in the future. If it makes your tests harder to debug, or
  conversely provides you with big speedups, `please let us know
  <https://github.com/python-trio/pytest-trio/issues/57>`__.)

* Integration with the fabulous `Hypothesis
  <https://hypothesis.works/>`__ library, so your async tests can use
  property-based testing: just use ``@given`` like you're used to.

* Support for testing projects that use Trio exclusively and want to
  use pytest-trio everywhere, and also for testing projects that
  support multiple async libraries and only want to enable
  pytest-trio's features for a subset of their test suite.


Vital statistics
================

* Install: ``pip install pytest-trio``

* Documentation: https://pytest-trio.readthedocs.io

* Issue tracker, source code: https://github.com/python-trio/pytest-trio

* License: MIT or Apache 2, your choice

* Contributor guide: https://trio.readthedocs.io/en/latest/contributing.html

* Code of conduct: Contributors are requested to follow our `code of
  conduct
  <https://trio.readthedocs.io/en/latest/code-of-conduct.html>`__ in
  all project spaces.

.. toctree::
   :maxdepth: 2

   quickstart.rst
   reference.rst

.. toctree::
   :maxdepth: 1

   history.rst

====================
 Indices and tables
====================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
* :ref:`glossary`
