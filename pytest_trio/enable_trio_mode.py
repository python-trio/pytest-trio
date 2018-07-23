__all__ = ["pytest_collection_modifyitems"]

from .plugin import automark


def pytest_collection_modifyitems(items):
    automark(items)
