from __future__ import annotations
import socket
from typing import Coroutine, Tuple, Union
from . import base_loop

BaseLoop = base_loop.BaseLoop

class Socket:

    sock: socket.socket
    _loop: BaseLoop

    def __init__(self, sock: socket.socket, loop: BaseLoop=None) -> None:
        self.sock = sock
        self._loop = loop
        
        if not loop:
            self._loop = base_loop.get_loop()
            
        self._loop.socket_accept(sock)
    
    def close(self) -> None:
        self.sock.close()
    
    async def connect(self, address: Union[Tuple, str, bytes]) -> Coroutine[Socket, None, None]:
        try:
            code = self.sock.connect_ex(address)
            if not code in (0,10035):
                raise RuntimeError(socket.errorTab[code])
        except:
            raise

        waiter = self._loop.create_future()

        def _done(key, mask):
            waiter.set_result(True)

        self._loop._selector.register(self.sock.fileno(), 1, _done)

        await waiter
        self._loop._selector.unregister(self.sock.fileno())
    
    async def recv(self, buffsize: int) -> Coroutine[bytes, None, None]:

        waiter = self._loop.create_future()

        def _done(key, mask):
            waiter.set_result(True)

        self._loop._selector.register(self.sock.fileno(), 1, _done)
        await waiter
        self._loop._selector.unregister(self.sock.fileno())
        data = self._loop.socket_recv(self.sock)
        return data
    
    def __enter__(self) -> None:
        pass

    def __exit__(self, *exc) -> None:
        self.close()