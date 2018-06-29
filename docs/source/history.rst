Release history
===============

.. currentmodule:: pytest_trio

.. towncrier release notes start

Pytest_Trio 0.4.2 (2018-06-29)
------------------------------

Features
~~~~~~~~

- pytest-trio now integrates with `Hypothesis
  <https://hypothesis.readthedocs.io>`_ to support ``@given`` on async tests
  using Trio. (`#42 <https://github.com/python-trio/pytest-trio/issues/42>`__)


Pytest_Trio 0.4.1 (2018-04-14)
------------------------------

No significant changes.


Pytest_Trio 0.4.0 (2018-04-14)
------------------------------

- Fix compatibility with trio 0.4.0 (`#25
  <https://github.com/python-trio/pytest-trio/pull/36>`__)


Pytest_Trio 0.3.0 (2018-01-03)
------------------------------

Features
~~~~~~~~

- Add ``nursery`` fixture and improve teardown handling for yield fixture (`#25
  <https://github.com/python-trio/pytest-trio/issues/25>`__)


Pytest_Trio 0.2.0 (2017-12-15)
------------------------------

- Heavy improvements, add async yield fixture, fix bugs, add tests etc. (`#17
  <https://github.com/python-trio/pytest-trio/issues/17>`__)


Deprecations and Removals
~~~~~~~~~~~~~~~~~~~~~~~~~

- Remove unused_tcp_port{,_factory} fixtures (`#15
  <https://github.com/python-trio/pytest-trio/issues/15>`__)


Pytest_Trio 0.1.1 (2017-12-08)
------------------------------

Disable intersphinx for trio (cause crash in CI for the moment due to 404
in readthedoc).


Pytest_Trio 0.1.0 (2017-12-08)
------------------------------

Initial release.
