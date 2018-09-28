Release history
===============

.. currentmodule:: pytest_trio

.. towncrier release notes start

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
