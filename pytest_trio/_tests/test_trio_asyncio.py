import pytest
import sys
import asyncio
from async_generator import async_generator, yield_

if sys.version_info < (3, 6):
    pytestmark = pytest.mark.skip(
        reason="trio-asyncio doesn't seem to work on 3.5"
    )
else:
    import trio_asyncio


async def use_run_asyncio():
    await trio_asyncio.run_asyncio(asyncio.sleep, 0)


@pytest.fixture()
@async_generator
async def asyncio_loop():
    async with trio_asyncio.open_loop() as loop:
        await yield_(loop)


@pytest.fixture()
@async_generator
async def asyncio_fixture_with_fixtured_loop(asyncio_loop):
    await use_run_asyncio()
    await yield_()


@pytest.fixture()
@async_generator
async def asyncio_fixture_own_loop():
    async with trio_asyncio.open_loop():
        await use_run_asyncio()
        await yield_()


@pytest.mark.trio
async def test_no_fixture():
    async with trio_asyncio.open_loop():
        await use_run_asyncio()


@pytest.mark.trio
async def test_half_fixtured_asyncpg_conn(asyncio_fixture_own_loop):
    await use_run_asyncio()


@pytest.mark.trio
async def test_fixtured_asyncpg_conn(asyncio_fixture_with_fixtured_loop):
    await use_run_asyncio()
