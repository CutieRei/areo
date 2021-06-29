from __future__ import annotations
from typing import Callable, List

class Handle:

    """
    a wrapper for callbacks in the event loop
    """

    _cancelled: bool
    _fn: Callable
    _args: List

    def __init__(self, fn: Callable, args: list) -> None:
        self._fn = fn
        self._args = args
        self._cancelled = False
    
    def __repr__(self) -> str:
        start, end = "<{0} ".format(type(self).__name__), ">"
        messages = []
        if self.cancelled():
            messages.append("cancelled")
        messages.append("callback={0}".format(self._fn))
        return start + " ".join(messages) + end
    
    def _run(self) -> None:
        try:
            self._fn(*self._args)
        except (SystemExit, KeyboardInterrupt):
            raise
        except BaseException:
            pass

    def cancel(self) -> None:
        self._cancelled = True
    
    def cancelled(self) -> bool:
        return self._cancelled

class TimedHandle(Handle):

    """
    a timed handler which provides callback execution at a certain time
    """

    _when: float

    def __init__(self, when: float, fn: Callable, args: list) -> None:
        super().__init__(fn, args)
        self._when = when
    
    def __repr__(self) -> str:
        start, end = "<{0} ".format(type(self).__name__), ">"
        messages = []
        if self.cancelled():
            messages.append("cancelled")
        else:
            messages.append("when={0}".format(self._when))
        messages.append("callback={0}".format(self._fn))
        return start + " ".join(messages) + end
    
    def when(self) -> float:
        return self._when
    
    def __hash__(self) -> int:
        return hash(self.when())
    
    def __le__(self, o: TimedHandle) -> bool:
        return self.when() <= o.when()
    
    def __ge__(self, o: TimedHandle) -> bool:
        return self.when() >= o.when()
    
    def __lt__(self, o: TimedHandle) -> bool:
        return self.when() < o.when()

    def __gt__(self, o: TimedHandle) -> bool:
        return self.when() > o.when()
    
    def __eq__(self, o: TimedHandle) -> bool:
        return self.when() == o.when()