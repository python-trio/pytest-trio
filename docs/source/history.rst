Release history
===============

.. currentmodule:: pytest_trio

.. towncrier release notes start

pytest-trio 0.8.0 (2022-11-01)
------------------------------

Features
~~~~~~~~

- If a test raises an ``ExceptionGroup`` (or nested ``ExceptionGroup``\ s) with only
  a single 'leaf' exception from ``pytest.xfail()`` or ``pytest.skip()``\ , we now
  unwrap it to have the desired effect on Pytest.  ``ExceptionGroup``\ s with two or
  more leaf exceptions, even of the same type, are not changed and will be treated
  as ordinary test failures.

  See `pytest-dev/pytest#9680 <https://github.com/pytest-dev/pytest/issues/9680>`__
  for design discussion.  This feature is particularly useful if you've enabled
  `the new strict_exception_groups=True option
  <https://trio.readthedocs.io/en/stable/reference-core.html#strict-versus-loose-exceptiongroup-semantics>`__. (`#104 <https://github.com/python-trio/pytest-trio/issues/104>`__)


Bugfixes
~~~~~~~~

- Fix an issue where if two fixtures are being set up concurrently, and
  one crashes and the other hangs, then the test as a whole would hang,
  rather than being cancelled and unwound after the crash. (`#120 <https://github.com/python-trio/pytest-trio/issues/120>`__)


Misc
~~~~

- Trio 0.22.0 deprecated ``MultiError`` in favor of the standard-library
  (or `backported <https://pypi.org/project/exceptiongroup/>`__) ``ExceptionGroup``
  type; ``pytest-trio`` now uses ``ExceptionGroup`` exclusively and therefore requires
  Trio 0.22.0 or later. (`#128 <https://github.com/python-trio/pytest-trio/issues/128>`__)

- Dropped support for end-of-life Python 3.6, and the ``async_generator`` library
  necessary to support it, and started testing on Python 3.10 and 3.11. (`#129 <https://github.com/python-trio/pytest-trio/issues/129>`__)


pytest-trio 0.7.0 (2020-10-15)
------------------------------

Features
~~~~~~~~

- Support added for :ref:`alternative Trio run functions <trio-run-config>` via the ``trio_run`` configuration variable and ``@pytest.mark.trio(run=...)``.  Presently supports Trio and QTrio. (`#105 <https://github.com/python-trio/pytest-trio/issues/105>`__)


Deprecations and Removals
~~~~~~~~~~~~~~~~~~~~~~~~~

- Python 3.5 support removed. (`#96 <https://github.com/python-trio/pytest-trio/issues/96>`__)


pytest-trio 0.6.0 (2020-05-20)
----------------------------------

Features
~~~~~~~~

- Incompatible change: if you use ``yield`` inside a Trio fixture, and
  the ``yield`` gets cancelled (for example, due to a background task
  crashing), then the ``yield`` will now raise :exc:`trio.Cancelled`.
  See :ref:`cancel-yield` for details. Also, in this same case,
  pytest-trio will now reliably mark the test as failed, even if the
  fixture doesn't go on to raise an exception. (`#75 <https://github.com/python-trio/pytest-trio/issues/75>`__)

- Updated for compatibility with Trio v0.15.0.


pytest-trio 0.5.2 (2019-02-13)
------------------------------

Features
~~~~~~~~

- pytest-trio now makes the Trio scheduler deterministic while running
  inside a Hypothesis test.  Hopefully you won't see any change, but if
  you had scheduler-dependent bugs Hypothesis will be more effective now. (`#73 <https://github.com/python-trio/pytest-trio/issues/73>`__)

- Updated for compatibility with trio v0.11.0.

pytest-trio 0.5.1 (2018-09-28)
------------------------------

Bugfixes
~~~~~~~~

- The pytest 3.8.1 release broke pytest-trio's handling of trio tests
  defined as class methods. We fixed it again. (`#64 <https://github.com/python-trio/pytest-trio/issues/64>`__)


pytest-trio 0.5.0 (2018-08-26)
------------------------------

This is a major release, including a rewrite of large portions of the
internals. We believe it should be backwards compatible with existing
projects. Major new features include:

* "trio mode": no more writing ``@pytest.mark.trio`` everywhere!
* it's now safe to use nurseries inside fixtures (`#55
  <https://github.com/python-trio/pytest-trio/issues/55>`__)
* new ``@trio_fixture`` decorator to explicitly mark a fixture as a
  trio fixture
* a number of easy-to-make mistakes are now caught and raise
  informative errors
* the :data:`nursery` fixture is now 87% more magical

For more details, see the manual. Oh right, speaking of which: we
finally have a manual! You should read it.


pytest-trio 0.4.2 (2018-06-29)
------------------------------

Features
~~~~~~~~

- pytest-trio now integrates with `Hypothesis
  <https://hypothesis.readthedocs.io>`_ to support ``@given`` on async tests
  using Trio. (`#42 <https://github.com/python-trio/pytest-trio/issues/42>`__)


pytest-trio 0.4.1 (2018-04-14)
------------------------------

No significant changes.


pytest-trio 0.4.0 (2018-04-14)
------------------------------

- Fix compatibility with trio 0.4.0 (`#25
  <https://github.com/python-trio/pytest-trio/pull/36>`__)


pytest-trio 0.3.0 (2018-01-03)
------------------------------

Features
~~~~~~~~

- Add ``nursery`` fixture and improve teardown handling for yield fixture (`#25
  <https://github.com/python-trio/pytest-trio/issues/25>`__)


pytest-trio 0.2.0 (2017-12-15)
------------------------------

- Heavy improvements, add async yield fixture, fix bugs, add tests etc. (`#17
  <https://github.com/python-trio/pytest-trio/issues/17>`__)


Deprecations and Removals
~~~~~~~~~~~~~~~~~~~~~~~~~

- Remove unused_tcp_port{,_factory} fixtures (`#15
  <https://github.com/python-trio/pytest-trio/issues/15>`__)


pytest-trio 0.1.1 (2017-12-08)
------------------------------

Disable intersphinx for trio (cause crash in CI for the moment due to 404
in readthedoc).


pytest-trio 0.1.0 (2017-12-08)
------------------------------

Initial release.
