
import abc
import asyncio
import sys
import traceback
from typing import (Any, ClassVar, Coroutine, Literal, TypeVar)

from dubious.discord import api, enums, make
from websockets import client

class Core:
    """ Framework class for classes that handle asynchronous loops. """

    doDebug: ClassVar = True

    def debug(self, *message):
        """ Prints to the console debugging messages if `.doDebug` is True. """

        if self.doDebug:
            print(*message)

    t_CoroRet = TypeVar("t_CoroRet")
    async def runWithTimeout(self,
        coro: Coroutine[Any, Any, t_CoroRet]
    ) -> t_CoroRet | Literal[False]:

        try:
            return await asyncio.wait_for(coro, 1)
        except asyncio.TimeoutError:
            return False

    @abc.abstractmethod
    def getcoros(self) -> Coroutine[Any, Any, Any]:
        """ Gets each async function to run on start. """

    @abc.abstractmethod
    def set(self) -> None:
        """ Set the flag that says the loops are meant to be running. """

    @abc.abstractmethod
    def isRunning(self) -> bool:
        """ Gets whether the loops are meant to be running currently. """

    @abc.abstractmethod
    def clear(self) -> None:
        """ Clears the flag that says that the loops are meant to be running. """

    @abc.abstractmethod
    async def close(self):
        """ Runs cleanup for the loops (when stopping / an error occurs). """

    def start(self):
        """ Starts all loops in `self.getcoros()`. """

        self.set()
        loop = asyncio.get_event_loop()
        while self.isRunning():
            fut = asyncio.gather(
                *self.getcoros()
            )

            try:
                loop.run_until_complete(fut)
            except KeyboardInterrupt:
                self.debug("ctrl+c, canceling")
                self.clear()
            except Exception as e:
                self.debug(*traceback.format_exception(e))
            finally:
                fut.cancel()
                fut = asyncio.gather(
                    fut, self.close()
                )
                try:
                    loop.run_until_complete(fut)
                except asyncio.CancelledError:
                    pass

class Discore(Core):
    """ Contains the functionality necessary to keep a gateway client
        connection alive. """

    token: str
    intents: int
    _sq: asyncio.Queue[api.Payload]
    _rq: asyncio.Queue[api.Payload]

    # Defined after connection
    uri: str
    _ws: client.WebSocketClientProtocol
    connected: asyncio.Event

    # Defined after Hello payload
    _acked: asyncio.Event
    _heartrate: int
    _beating: asyncio.Event
    _last: int | None

    def __init__(self,
        token: str,
        intents: int,
        uri: str="wss://gateway.discord.gg/?v=9&encoding=json"
    ):
        self.token = token
        self.intents = intents
        self.uri = uri

        self._sq = asyncio.Queue()
        self._rq = asyncio.Queue()

        self.connected = asyncio.Event()
        self._acked = asyncio.Event()
        self._beating = asyncio.Event()
        self._last = None

    def getcoros(self):
        return (
            self._task_conn(),
            self._task_recv(),
            self._task_send(),
            self._task_beat(),
        )

    def set(self):
        self.connected.set()

    def isRunning(self):
        return self.connected.is_set()

    def clear(self):
        self._beating.clear()
        self.connected.clear()

    async def close(self):
        await self._ws.close()

    async def _task_conn(self):
        self._ws = await client.connect(self.uri)
        self.connected.set()
        #self.debug("Connected")

    async def _task_recv(self):
        """ Loop for recieving data from the websocket.

            Adds the recieved payload to the recv queue to be gotten and
            handled with `.recv`. """

        await self.connected.wait()

        while self.connected.is_set():
            data = await self.runWithTimeout(self._ws.recv())
            if data is None or data is False: continue

            payload = api.Payload.parse_raw(data)
            #self.debug(f"[R] {payload}")
            if payload.s:
                self.last = payload.s

            match payload.op:
                case enums.opcode.Hello:
                    cast: api.Hello = api.castInner(payload)  # type: ignore
                    self._heartrate = cast.heartbeat_interval
                    self._beating.set()
                    self._acked.set()
                    await self.send(self._identify())
                case enums.opcode.HeartbeatAck:
                    self._acked.set()
                case _:
                    await self._rq.put(payload)

    async def _task_send(self):
        """ Loop for sending data to the websocket. 

            Waits for a payload added to the queue with `.send`."""

        await self.connected.wait()

        while self.connected.is_set():
            payload = await self.runWithTimeout(self._sq.get())
            if payload is False: continue
            #self.debug(f"[S] {payload.json()}")
            await self._ws.send(payload.json())

    async def _task_beat(self):
        """ Loop for periodically adding an `opcode.Heartbeat` payload to the
            send queue. """

        await self.connected.wait()

        while self.connected.is_set():
            res = await self.runWithTimeout(self._beating.wait())
            if res is False: continue

            await self._acked.wait()
            await asyncio.sleep(self._heartrate / 1000)

            self._acked.clear()
            await self.send(self._heartbeat())

    def _heartbeat(self):
        """ Creates an `opcode.Heartbeat` payload based on the last sequence
            number sent by Discord. """

        return self.makePayload(
            enums.opcode.Heartbeat
        )

    def _identify(self):
        """ Creates an `opcode.Identify` payload to send to Discord upon
            recieving the `opcode.Hello` payload. Contains the bot user token
            and the desired intents for the bot user. """

        return self.makePayload(
            enums.opcode.Identify,
            make.Identify(
                token=self.token,
                intents=self.intents,
                properties={
                    "$os": sys.platform,
                    "$browser": "dubiousdiscord",
                    "$device": "dubiousdiscord"
                }
            )
        )

    def makePayload(self, code: enums.codes, d: api.t_APIData=None):
        """ Creates a `Payload` that includes the last sequence number sent by
            Discord. """

        return api.Payload(
            op=code if isinstance(code, enums.opcode)
                else enums.opcode.Dispatch,
            t=code if isinstance(code, enums.tcode)
                else None,
            s=self._last,
            d=d
        )

    async def recv(self):
        """ Gets a `Payload` sent by Discord. """

        return await self._rq.get()

    async def send(self, payload: api.Payload):
        """ Puts a `Payload` into the send queue. """

        await self._sq.put(payload)
