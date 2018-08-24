__all__ = ["pytest_collection_modifyitems", "pytest_fixture_setup"]

from .plugin import automark, handle_fixture


def pytest_collection_modifyitems(items):
    automark(items)


def pytest_fixture_setup(fixturedef, request):
    return handle_fixture(fixturedef, request, force_trio_mode=True)
