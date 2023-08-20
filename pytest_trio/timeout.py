from __future__ import annotations
from typing import Optional
import warnings
import threading
import trio
import pytest
import pytest_timeout
from .traceback_format import format_recursive_nursery_stack


pytest_timeout_settings = pytest.StashKey[pytest_timeout.Settings]()
send_timeout_callable = None
send_timeout_callable_ready_event = threading.Event()


def set_timeout(item: pytest.Item) -> None:
    try:
        settings = item.stash[pytest_timeout_settings]
    except KeyError:
        # No timeout or not our timeout
        return

    if settings.func_only:
        warnings.warn(
            "Function only timeouts are not supported for trio based timeouts"
        )

    global send_timeout_callable

    # Shouldn't be racy, as xdist uses different processes
    if send_timeout_callable is None:
        threading.Thread(target=trio_timeout_thread, daemon=True).start()

    send_timeout_callable_ready_event.wait()

    send_timeout_callable(settings.timeout)


@pytest.hookimpl()
def pytest_timeout_set_timer(
    item: pytest.Item, settings: pytest_timeout.Settings
) -> Optional[bool]:
    if item.get_closest_marker("trio") is not None and item.config.getini(
        "trio_timeout"
    ):
        item.stash[pytest_timeout_settings] = settings
        return True


# No need for pytest_timeout_cancel_timer as we detect that the test loop has exited


def trio_timeout_thread():
    async def run_timeouts():
        async with trio.open_nursery() as nursery:
            token = trio.lowlevel.current_trio_token()

            async def wait_timeout(token: trio.TrioToken, timeout: float) -> None:
                await trio.sleep(timeout)

                try:
                    token.run_sync_soon(
                        lambda: trio.lowlevel.spawn_system_task(execute_timeout)
                    )
                except RuntimeError:
                    # test has finished
                    pass

            def send_timeout(timeout: float):
                test_token = trio.lowlevel.current_trio_token()
                token.run_sync_soon(
                    lambda: nursery.start_soon(wait_timeout, test_token, timeout)
                )

            global send_timeout_callable
            send_timeout_callable = send_timeout
            send_timeout_callable_ready_event.set()

            await trio.sleep_forever()

    trio.run(run_timeouts)


async def execute_timeout() -> None:
    if pytest_timeout.is_debugging():
        return

    nursery = get_test_nursery()
    stack = "\n".join(format_recursive_nursery_stack(nursery) + ["Timeout reached"])

    async def report():
        pytest.fail(stack, pytrace=False)

    nursery.start_soon(report)


def get_test_nursery() -> trio.Nursery:
    task = trio.lowlevel.current_task().parent_nursery.parent_task

    for nursery in task.child_nurseries:
        for task in nursery.child_tasks:
            if task.name.startswith("pytest_trio.plugin._trio_test_runner_factory"):
                return task.child_nurseries[0]

    raise Exception("Could not find test nursery")
