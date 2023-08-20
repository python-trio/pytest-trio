from __future__ import annotations
from trio.lowlevel import Task
from itertools import chain
import traceback


def format_stack_for_task(task: Task, prefix: str) -> list[str]:
    stack = list(task.iter_await_frames())

    nursery_waiting_children = False

    for i, (frame, lineno) in enumerate(stack):
        if frame.f_code.co_name == "_nested_child_finished":
            stack = stack[: i - 1]
            nursery_waiting_children = True
            break
        if frame.f_code.co_name == "wait_task_rescheduled":
            stack = stack[:i]
            break
        if frame.f_code.co_name == "checkpoint":
            stack = stack[:i]
            break

    stack = (frame for frame in stack if "__tracebackhide__" not in frame[0].f_locals)

    ss = traceback.StackSummary.extract(stack)
    formated_traceback = list(
        map(lambda x: prefix + x[2:], "".join(ss.format()).splitlines())
    )

    if nursery_waiting_children:
        formated_traceback.append(prefix + "Awaiting completion of children")
    formated_traceback.append(prefix)

    return formated_traceback


def format_task(task: Task, prefix: str = "") -> list[str]:
    lines = []

    subtasks = list(
        chain(*(child_nursery.child_tasks for child_nursery in task.child_nurseries))
    )

    if subtasks:
        trace_prefix = prefix + "│"
    else:
        trace_prefix = prefix + " "

    lines.extend(format_stack_for_task(task, trace_prefix))

    for i, subtask in enumerate(subtasks):
        if (i + 1) != len(subtasks):
            lines.append(f"{prefix}├ {subtask.name}")
            lines.extend(format_task(subtask, prefix=f"{prefix}│ "))
        else:
            lines.append(f"{prefix}└ {subtask.name}")
            lines.extend(format_task(subtask, prefix=f"{prefix}  "))

    return lines


def format_recursive_nursery_stack(nursery) -> list[str]:
    stack = []

    for task in nursery.child_tasks:
        stack.append(task.name)
        stack.extend(format_task(task))

    return stack
