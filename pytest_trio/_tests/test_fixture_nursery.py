import pytest
import trio


async def handle_client(stream):
    while True:
        buff = await stream.receive_some(4)
        await stream.send_all(buff)


@pytest.fixture
async def server(nursery):
    listeners = await nursery.start(trio.serve_tcp, handle_client, 0)
    return listeners[0]


@pytest.mark.trio
async def test_try(server):
    stream = await trio.testing.open_stream_to_socket_listener(server)
    await stream.send_all(b"ping")
    rep = await stream.receive_some(4)
    assert rep == b"ping"
