import pytest
import trio_asyncio
import asyncio


@trio_asyncio.trio2aio
async def work_in_asyncio():
    await asyncio.sleep(0)


@pytest.fixture()
async def asyncio_loop():
    async with trio_asyncio.open_loop() as loop:
        yield loop


@pytest.fixture()
async def asyncio_fixture_with_fixtured_loop(asyncio_loop):
    await work_in_asyncio()
    yield 42


@pytest.fixture()
async def asyncio_fixture_own_loop():
    async with trio_asyncio.open_loop():
        await work_in_asyncio()
        yield 42


@pytest.mark.trio
async def test_no_fixture():
    async with trio_asyncio.open_loop():
        await work_in_asyncio()


@pytest.mark.trio
async def test_half_fixtured_asyncpg_conn(asyncio_fixture_own_loop):
    await work_in_asyncio()


@pytest.mark.trio
async def test_fixtured_asyncpg_conn(asyncio_fixture_with_fixtured_loop):
    await work_in_asyncio()
