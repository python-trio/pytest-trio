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

* Useful fixtures included: use ``autojump_clock`` for easy testing of
  code with timeouts.

* Write your own async fixtures: start up a Trio-based server inside a
  fixture, and then connect to it from your test.

* Use `Hypothesis <https://hypothesis.works/>`__? This plugin
  integrates with Hypothesis, so your async tests can use
  property-based testing.


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
