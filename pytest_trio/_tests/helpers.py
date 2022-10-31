import pytest


def enable_trio_mode_via_pytest_ini(testdir):
    testdir.makefile(".ini", pytest="[pytest]\ntrio_mode = true\n")


def enable_trio_mode_trio_run_via_pytest_ini(testdir):
    testdir.makefile(".ini", pytest="[pytest]\ntrio_mode = true\ntrio_run = trio\n")


def enable_trio_mode_via_conftest_py(testdir):
    testdir.makeconftest("from pytest_trio.enable_trio_mode import *")


enable_trio_mode = pytest.mark.parametrize(
    "enable_trio_mode",
    [
        enable_trio_mode_via_pytest_ini,
        enable_trio_mode_trio_run_via_pytest_ini,
        enable_trio_mode_via_conftest_py,
    ],
)
