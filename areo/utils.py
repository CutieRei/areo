import inspect
from typing import Any, Coroutine, List, Set, Tuple, Union
from . import base_loop
from . import futures

Future = futures.Future
Task = futures.Task

async def wait(fs: List[Union[Future, Task, Coroutine]], loop: base_loop.BaseLoop=None, timeout: Union[int, float]=None) -> Tuple[Set[Union[Future, Task]],Set[Union[Future, Task]]]:

    assert isinstance(timeout, (int, float)) or timeout is None

    if loop is None:
        loop = base_loop.get_loop()

    for fut in fs:
        if not (isinstance(fut, (Future, Task)) or inspect.iscoroutine(fut)):
            raise ValueError("expected Future, Task, or Coroutine. got '{0}' instead".format(type(fut)))

    counts = len(fs)

    waiter = loop.create_future()
    done: Set[Union[Future, Task]] = set()
    pending: Set[Union[Future, Task]] = set()

    def _on_completion(fut):
        nonlocal counts
        counts -= 1
        done.add(fut)
        if counts <= 0:
            waiter.set_result(True)
    
    def _timeout():
        waiter.set_result(True)
        nonlocal pending, done
        pending = done ^ pending
    

    for fut in fs:
        if inspect.iscoroutine(fut):
            fut = loop.create_task(fut)
        fut.add_done_callback(_on_completion)
        pending.add(fut)

    if timeout:
        loop.call_later(timeout, _timeout)
    

    await waiter
    return done, pending

async def sleep(delay: Union[int, float], result=True, loop: base_loop.BaseLoop=None) -> Coroutine[Any, None, None]:
    
    if loop is None:
        loop = base_loop.get_loop()

    waiter = loop.create_future()

    if delay <= 0:
        loop.call_soon(waiter.set_result, result)
    else:
        loop.call_later(delay, waiter.set_result, result)
    return await waiter

async def wait_for(fut: Union[Future, Task, Coroutine], timeout: Union[int, float], loop: base_loop.BaseLoop=None) -> Coroutine[Any, None, None]:

    if loop is None:
        loop = base_loop.get_loop()

    waiter = loop.create_future()

    if inspect.iscoroutine(fut):
        fut = loop.create_task(fut)
    
    handle = loop.call_later(timeout, waiter.set_result, False)

    def _done(fut):
        waiter.set_result(True)
    
    fut.add_done_callback(_done)

    res = await waiter
    if res:
        return fut.result()
    else:
        raise RuntimeError("Timed out")
