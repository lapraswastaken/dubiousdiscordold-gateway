
import asyncio
import math
import re
from typing import Any, Callable, ClassVar, Coroutine, TypeGuard, TypeVar
from typing_extensions import Self
from dubious.GuildStructure import Item, Many, One, Structure

from dubious.discord import api, enums, make, rest
from dubious.discord.core import Core, Discore
from dubious.Interaction import Ixn
from dubious.Machines import Command, Handle, Machine, Option, Subcommand

t_Handler = Callable[
    [enums.codes, api.Payload],
        Coroutine[Any, Any, None]]

class Chip(Core):
    """ Handles the connection to Discord and other core functionalities.

        Uses a Discore to connect to Discord, and has the same protocols for
        running loops in (mock) parallel. Handler functions can be added to a
        Chip that get called whenever a payload is recieved from Discord through
        the Discore. """

    _core: Discore
    _handlers: list[t_Handler]

    running: asyncio.Event

    def __init__(self):
        self._handlers = []

    @property
    def chip(self): return self
    @property
    def core(self): return self._core

    def getcoros(self):
        return self._core.getcoros() + (
            self._loop_dispatch(),
        )

    async def _loop_dispatch(self):
        await self.running.wait()

        while self.running.is_set():
            payload = await self.runWithTimeout(self._core.recv())
            if payload is False: continue

            code = payload.t if payload.t else payload.op
            if not isinstance(code, (enums.opcode, enums.tcode)): continue

            for handler in self._handlers:
                await handler(code, payload)

    def set(self):
        self.running.set()

    def isRunning(self):
        return self.running.is_set()

    def clear(self):
        self.running.clear()

    async def close(self):
        await self.core.close()

    def start(self, token: str, intents: int):
        """ Instantiates a `Discore` and starts it and itself. Until a
            `KeyboardInterrupt` happens, it will attempt to restart the
            `Discore` and itself whenever an error is encountered. """

        self.running = asyncio.Event()
        self._core = Discore(token, intents)
        super().start()

    def addHandler(self, func: t_Handler):
        """ Adds a function to be called whenever a Payload is recieved. """

        self._handlers.append(func)

class Pory:
    """ A collection of `Handle`-wrapped methods that uses a Chip to handle
        raw payloads from Discord. 

        Pre-defined is a method called when the `Chip` catches a `tcode.Ready`
        payload. This method sets the `Pory`'s `user`, its `guildIDs`, and its
        `http` api connection. """

    handles: dict[enums.codes, list[Handle]]

    def __init_subclass__(cls):
        cls.handles = Handle.collectByReference(cls)

    chip: Chip
    up: "Pory | None"

    _user: api.User
    _guildIDs: set[api.Snowflake]

    http: rest.Http

    @property
    def user(self): return self._user
    @property
    def guildIDs(self): return self._guildIDs

    @property
    def id(self): return self._user.id
    @property
    def token(self): return self.chip.core.token

    def use(self, chip: Chip | Self):
        """ Tells the `Pory` to use a specific Chip. If another `Pory` is given
            instead, uses that `Pory`'s `Chip`. """

        if isinstance(chip, Pory):
            self.chip = chip.chip
        else:
            self.chip = chip
        self.chip.addHandler(self._handle)
        return self

    async def _handle(self, code: enums.codes, payload: api.Payload):
        handlers = self.__class__.handles.get(code)
        if not handlers: return

        d = api.castInner(payload)
        for handler in handlers:
            await handler.teg()(self, d)

    @Handle(enums.tcode.Ready, -100)
    async def ready(self, ready: api.Ready):
        """ Sets the `Pory`'s `user`, its `guildIDs`, and instantiates an `http`
            api framework. """

        self._user = ready.user
        self._guildIDs = {g.id for g in ready.guilds}
        self.http = rest.Http(self.user.id, self.token)
