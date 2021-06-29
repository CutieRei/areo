import collections
import socket
import threading
import time
import heapq
from . import futures
from .handlers import Handle, TimedHandle
from typing import Any, Literal, Callable, Coroutine, List, NoReturn, Tuple, Union
import selectors

_MAX_SELECT_TIMEOUT = 5 * 3600
Task = futures.Task
Future = futures.Future

class _Loops(threading.local):
    loop = None
    called = False

class _RunningLoops(threading.local):
    loop = None

_loops = _Loops()
_running_loop = _RunningLoops()

class AbstractLoop:

    """
    The abstract class for Event Loop
    consider subclassing BaseLoop for pre built functionality
    """

    _timed_handlers: List[TimedHandle]
    _handlers: collections.deque[Handle]
    _current_task: Task
    _closed: bool
    _stopping: bool
    _selector: selectors.DefaultSelector
    _ssock: socket.socket
    _csock: socket.socket
    
    def __init__(self) -> None:
        pass
    
    def close(self) -> NoReturn:
        """
        closes the loop, after this function call scheduling wont be possible,
        if the loop is closed this function returns immediately
        """
        raise NotImplementedError()
    
    def stop(self) -> NoReturn:
        """
        stop the loop, if the loop is not running this function returns immediately
        """
        raise NotImplementedError()

    def create_task(self, coro: Union[Coroutine, Task]) -> NoReturn:
        """
        create a task and schedule it to be run in the next iteration of the loop,
        if `coro` is a Task this function returns immediately, if the Task is attached to a diffrent loop
        this function raises RuntimeError
        """
        raise NotImplementedError()
    
    def create_future(self) -> NoReturn:
        """
        equivalent to `areo.Future(loop)`
        """
        raise NotImplementedError()
    
    def call_soon(self, fn: Callable, *args) -> NoReturn:
        """
        schedule a callback to be ran in the next iteration,
        we suggest using `functools.partial` for keyword argument since this function does not
        provide keyword argument for the callback
        """
        raise NotImplementedError()
    
    def call_at(self, when: float, fn: Callable, *args) -> NoReturn:
        """
        schedule a callback to be called at a specific time using `time.monotonic`,
        we suggest using `functools.partial` for keyword argument since this function does not
        provide keyword argument for the callback
        """
        raise NotImplementedError()
    
    def call_later(self, delay: Union[float, int], fn: Callable, *args) -> NoReturn:
        """
        equivalent to `loop.call_at(loop.time() + delay, fn)`
        """
        raise NotImplementedError()
    
    def call_soon_threadsafe(self, fn: Callable, *args) -> NoReturn:
        """
        call_soon but with signal handler to wake up the event loop,
        this may be called from another thread
        """
        raise NotImplementedError()
    
    def run_forever(self) -> NoReturn:
        """
        run the event loop indefinitely
        """
        raise NotImplementedError()
        
    def time(self) -> NoReturn:
        """
        alias for `time.monotonic`
        """
        raise NotImplementedError()
    
    def run_until_done(self, coro: Union[Coroutine, Task, Future]) -> NoReturn:
        """
        run a coroutine or a task or a future until done,
        if `coro` is a coroutine it will be wrapped in a Task
        returns the Future result or raise Future exception
        """
        raise NotImplementedError()
    
    def socket_recv(self, sock: socket.socket) -> NoReturn:
        raise NotImplementedError()

    def socket_send(self, sock: socket.socket) -> NoReturn:
        raise NotImplementedError()

    def socket_sendall(self, sock: socket.socket) -> NoReturn:
        raise NotImplementedError()
    
    def socket_accept(self, sock: socket.socket) -> NoReturn:
        raise NotImplementedError()

    def _closed(self) -> NoReturn:
        raise NotImplementedError()
    
    def _run_once(self) -> NoReturn:
        raise NotImplementedError()
    
    def _check_closed(self) -> NoReturn:
        raise NotImplementedError()
    
    def _process_events(self, events: List[Tuple[selectors.SelectorKey, Union[Literal[1], Literal[2]]]]) -> NoReturn:
        raise NotImplementedError()

    def _write_self(self) -> NoReturn:
        raise NotImplementedError()
    
    def _read_self(self, *args) -> NoReturn:
        raise NotImplementedError()
    
    def _make_self_sock(self) -> NoReturn:
        raise NotImplementedError()
    
    def _add_handle(self, handle: Union[Handle, TimedHandle]) -> NoReturn:
        raise NotImplementedError()

    def _add_handle_signal(self, handle: Union[Handle, TimedHandle]) -> NoReturn:
        raise NotImplementedError()

class BaseLoop(AbstractLoop):

    def __init__(self) -> None:
        self._timed_handlers = []
        self._handlers = collections.deque()
        self._current_task = None
        self._closed = False
        self._stopping = False
        self._selector = selectors.DefaultSelector()
        self._make_self_sock()

    def stop(self) -> None:
        self._write_self()
        self._stopping = True

    def close(self) -> None:
        if not self._stopping:
            raise RuntimeError("loop must not be running to close")
        self._closed = True

    def socket_accept(self, sock: socket.socket) -> socket.socket:
        sock.setblocking(False)
        return sock
    
    def socket_recv(self, sock: socket.socket) -> Union[bytes, None]:
        if sock.getblocking():
            raise RuntimeError("socket must not be blocking")
        data = b""
        while True:
            try:
                buff = sock.recv(4096)
                if not buff:
                    break
                data += buff
            except OSError:
                break
            except BlockingIOError:
                return None
            except:
                raise
        return data
    
    def _check_closed(self) -> Union[bool, NoReturn]:
        if self._closed:
            raise RuntimeError("loop is closed")
        return True
    
    def _make_self_sock(self) -> None:
        ssock, csock = socket.socketpair()
        ssock.setblocking(False)
        csock.setblocking(False)
        self._ssock, self._csock = ssock, csock
        self._selector.register(ssock.fileno(), selectors.EVENT_READ, self._read_self)

    
    def _write_self(self) -> None:

        csock = self._csock
        if not csock:
            return
        try:
            csock.send(b"\0")
        except:
            pass
    
    def _read_self(self, *args) -> None:
        while True:
            try:
                data = self._ssock.recv(4096)
                if not data:
                    break
            except InterruptedError:
                continue
            except BlockingIOError:
                break

    def create_task(self, coro: Union[Coroutine, Task]) -> Task:
        if isinstance(coro, Task):
            if coro._loop != self:
                raise RuntimeError("Task is attached to another loop")
            return coro
        task = Task(self, coro)
        return task
    
    def create_future(self) -> Future:
        return Future(self)

    def run_until_done(self, coro: Union[Coroutine, Task, Future]) -> Any:
        self._check_closed()
        if not isinstance(coro, (Future, Task)):
            task = self.create_task(coro)
        else:
            task = coro

        def _done(fut: Future):
            fut._loop.stop()

        task.add_done_callback(_done)
        try:
            self.run_forever()
        except:
            if not task.done():
                task.cancel()
        finally:
            return task.result()
    
    def _add_handle(self, handle: Union[Handle, TimedHandle]) -> None:
        if isinstance(handle, TimedHandle):
            heapq.heappush(self._timed_handlers, handle)
        elif isinstance(handle, Handle):
            self._handlers.append(handle)
    
    def _add_handle_signal(self, handle: Union[Handle, TimedHandle]) -> None:
        self._add_handle(handle)
        self._write_self()

    def call_soon(self, fn: Callable, *args) -> Handle:
        handle = Handle(fn, args)
        self._add_handle(handle)
        return handle
    
    def call_at(self, when: float, fn: Callable, *args) -> TimedHandle:
        handle = TimedHandle(when, fn, args)
        self._add_handle(handle)
        return handle
    
    def call_later(self, delay: Union[float, int], fn: Callable, *args) -> TimedHandle:
        return self.call_at(self.time()+delay, fn, *args)
    
    def call_soon_threadsafe(self, fn: Callable, *args) -> Handle:
        handle = self.call_soon(fn, *args)
        self._write_self()
        return handle
    
    def time(self) -> float:
        return time.monotonic()
    
    def _run_once(self) -> None:

        timeout = None
        if self._handlers or self._stopping:
            timeout = 0
        elif self._timed_handlers:
            timeout = self._timed_handlers[0]._when
            timeout = min(max(0, timeout-self.time()), _MAX_SELECT_TIMEOUT)
        
        try:
            events = self._selector.select(timeout)
            self._process_events(events)
        except:
            pass

        end = self.time()
        while self._timed_handlers:
            handle = self._timed_handlers[0]
            if handle._when >= end:
                break
            handle = heapq.heappop(self._timed_handlers)
            self._handlers.append(handle)
        
        for _ in range(len(self._handlers)):
            handle: Union[Handle, TimedHandle] = self._handlers.popleft()
            if handle._cancelled:
                continue
            handle._run()

        handle = None
    
    def _process_events(self, events: List[Tuple[selectors.SelectorKey, Union[Literal[1], Literal[2]]]]) -> None:
        for key, mask in events:
            self.call_soon(key.data, key.fileobj, mask)
    
    def run_forever(self) -> None:
        self._check_closed()
        set_loop(self)
        _set_running_loop(self)
        while True:
            try:
                self._run_once()
                if self._stopping:
                    self._stopping = False
                    break
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                raise
            finally:
                _set_running_loop(None)

def new_loop() -> BaseLoop:
    return BaseLoop()

def set_loop(loop: AbstractLoop) -> None:
    _loops.called = True
    _loops.loop = loop

def get_loop() -> BaseLoop:

    if _loops.loop is None and not _loops.called and threading.current_thread() == threading.main_thread():
        set_loop(new_loop())
    elif _loops.loop is None:
        raise RuntimeError("No current loop")
    return _loops.loop

def running_loop() -> BaseLoop:

    loop = _running_loop.loop
    if loop is None:
        raise RuntimeError("No running loop")
    return loop

def _set_running_loop(loop: AbstractLoop) -> None:
    _running_loop.loop = loop

def create_task(coro: Union[Coroutine, Task]) -> Task:
    loop = running_loop()
    return loop.create_task(coro)