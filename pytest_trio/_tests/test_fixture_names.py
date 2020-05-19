import pytest
from pytest_trio import trio_fixture
import trio


@trio_fixture
def fixture_with_unique_name(nursery):
    nursery.start_soon(trio.sleep_forever)


@pytest.mark.trio
async def test_fixture_names(fixture_with_unique_name):
    # This might be a bit fragile ... if we rearrange the nursery hierarchy
    # somehow so it breaks, then we can make it more robust.
    task = trio.lowlevel.current_task()
    assert task.name == "<test 'test_fixture_names'>"
    sibling_names = {task.name for task in task.parent_nursery.child_tasks}
    assert "<fixture 'fixture_with_unique_name'>" in sibling_names
