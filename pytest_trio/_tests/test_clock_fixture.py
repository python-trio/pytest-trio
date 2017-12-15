import pytest
import trio


@pytest.mark.trio
async def test_sleep_with_autojump_clock(autojump_clock):
    assert trio.current_time() == 0

    for i in range(10):
        start_time = trio.current_time()
        await trio.sleep(i)
        end_time = trio.current_time()

        assert end_time - start_time == i
