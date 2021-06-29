from __future__ import annotations
from . import base_loop
from typing import Any, Callable, Coroutine, Generator, List, NoReturn, Union
import enum

class State(enum.Enum):
    PENDING = 0
    FINISHED = 1
    CANCELLED = 2

_PENDING = State.PENDING
_FINISHED = State.FINISHED
_CANCELLED = State.CANCELLED

class Future:

    """
    a future class that provide switching task to let the event loop run other task while
    waiting until a Future object is done
    """
    
    _loop: base_loop.BaseLoop
    _state: Union[_PENDING, _FINISHED, _CANCELLED]
    _result: Any
    _exception: Union[BaseException, None]
    _callbacks: List[Callable[[Future]]]
    _cancel_msg: str
    _callbacks: List[Callable[[Future]]]
    
    def __init__(self, loop: base_loop.BaseLoop) -> None:
        self._loop = loop
        self._state = _PENDING
        self._result = None
        self._exception = None
        self._cancel_msg = "Future is cancelled"
        self._callbacks = []

    def __await__(self) -> Generator[Future, None, None]:
        if not self.done():
            yield self
        if not self.done():
            raise RuntimeError("Future is not awaited")
        return self.result()
    
    def _check_done(self) -> Union[bool, NoReturn]:
        if self._state != _PENDING:
            raise RuntimeError("Future is done")
        return False
    
    def done(self) -> bool:
        return self._state != _PENDING
    
    def cancelled(self) -> bool:
        return self._state == _CANCELLED
    
    def cancel(self, msg=None):
        if self._state == _CANCELLED:
            return
        self._state = _CANCELLED
        self._cancel_msg = msg or self._cancel_msg
        self._schedule_callbacks()
    
    def _raise_cancel_error(self) -> NoReturn:
        raise RuntimeError(self._cancel_msg)
        
    def result(self) -> Any:
        """
        returns the result of the Future object, if the result is not set then this function
        raises an exception, and if the exception is set this function will raise the exception
        correspondingly and will raise exception when Future is cancelled
        """
        if not self.done():
            raise RuntimeError("Result is not available")
        if self.cancelled():
            self._raise_cancel_error()
        if self._exception:
            raise self._exception
        return self._result
    
    def exception(self) -> BaseException:
        """
        returns the exception of this Future object, if the exception is not set then this function will
        raise an exception and raises exception when Future is cancelled
        """
        if not self.done():
            raise RuntimeError("Exception is not set")
        if self.cancelled():
            self._raise_cancel_error()
        return self._exception
    
    def _schedule_callbacks(self) -> None:
        
        callbacks = self._callbacks[:]
        if not callbacks:
            return
        self._callbacks = []

        for callback in callbacks:
            self._loop.call_soon(callback, self)
        self._loop._write_self()
    
    def add_done_callback(self, fn: Callable[[Future]]) -> None:
        """
        add a done callback to be ran after the future is finished or cancelled
        """
        self._check_done()
        self._callbacks.append(fn)
    
    def remove_done_callback(self, fn: Callable[[Future]]) -> None:
        """
        removes a callback from the `done callback`, if the callback is not in the `done callback`
        then this function returns immediately
        """
        self._check_done()
        if fn in self._callbacks:
            self._callbacks.remove(fn)
    
    def set_result(self, res) -> None:
        """
        set the result of the Future, raises exception when Future is cancelled
        """
        if self.cancelled():
            self._raise_cancel_error()
        self._state = _FINISHED
        self._result = res
        self._schedule_callbacks()
    
    def set_exception(self, exc) -> None:
        """
        set the exception of the Future, raises exception when Future is cancelled
        """
        if self.cancelled():
            self._raise_cancel_error()
        self._state = _FINISHED
        self._exception = exc
        self._schedule_callbacks()
    
    __iter__ = __await__



class Task(Future):

    """
    a subclass of Future that provides running coroutines in the event loop
    """
    
    coro: Coroutine

    def __init__(self, loop: base_loop.BaseLoop, coro: Coroutine) -> None:
        super().__init__(loop)
        self._coro = coro
        self._cancel_msg = "Task is cancelled"
        self._loop.call_soon(self._step)

    def set_result(self, res) -> NoReturn:
        raise RuntimeError("Task does not support setting result")
    
    def set_exception(self, exc) -> NoReturn:
        raise RuntimeError("Task does not support setting exception")
    
    def _step(self) -> None:
        if self._state != _PENDING:
            return
        self._loop._current_task = self
        try:
            res = self._coro.send(None)
            if isinstance(res, Future):
                def _done(future: Future):
                    self._step()
                res.add_done_callback(_done)
            else:
                RuntimeError("got unexpected object '{0}'".format(type(res)))
        except StopIteration as exc:
            super().set_result(exc.value)
        except BaseException as exc:
            super().set_exception(exc)
        finally:
            self._loop._current_task = None

