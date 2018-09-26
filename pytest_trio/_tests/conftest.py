# Temporary hack while waiting for an answer here:
#    https://github.com/pytest-dev/pytest/issues/4039
import pytest
import warnings
warnings.filterwarnings(
    "default",
    category=pytest.RemovedInPytest4Warning,
    message=".*non-top-level conftest.*",
)

pytest_plugins = ["pytester"]
