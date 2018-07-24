"""Top-level package for pytest-trio."""

from ._version import __version__
from .plugin import trio_fixture

__all__ = ["trio_fixture"]
