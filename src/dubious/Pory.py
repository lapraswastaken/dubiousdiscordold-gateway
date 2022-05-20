
import asyncio
from typing import Any, Callable, ClassVar, Coroutine, TypeVar
from typing_extensions import Self

from dubious.discord import api, enums, make, rest
from dubious.discord.core import Core, Discore
from dubious.Interaction import Ixn
from dubious.Machines import Command, Handle, Machine, Option

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
        handler = Handle.get(self).get(code)
        if not handler: return

        d = api.cast(payload)
        await handler.call(self, d)

    @Handle(enums.tcode.Ready)
    async def ready(self, ready: api.Ready):
        """ Sets the `Pory`'s `user`, its `guildIDs`, and instantiates an `http`
            api framework. """

        self._user = ready.user
        self._guildIDs = {g.id for g in ready.guilds}
        self.http = rest.Http(self.user.id, self.token)

class Pory2(Pory):
    """ A collection of `Command`-wrapped methods that registers each method as
        a Discord Application Command. Also collects `Handle`s.

        Pre-defined is a method called when the `Chip` catches a `tcode.Ready`
        payload. This method automatically registers all `Command`s via the
        `http` api.
        Also pre-defined is a method called when the `Chip` catches a
        `tcode.InteractionCreate` payload. This method calls the coresponding
        `Command` method on this `Pory2`.

        For convenience, the `.TEST_IN` ClassVar will make all `Command`s in
        this Pory2 register in the guild with the specified ID. """

    TEST_IN: ClassVar[api.Snowflake | str | int | None] = None

    supercommand: ClassVar[Command | None] = None

    doPrintCommands: ClassVar = True
    def printCommand(self, *message):
        if self.doPrintCommands:
            print(*message)

    def use(self, chip: Chip | Self):
        if not isinstance(chip, Chip):
            supercommand = (
                chip.supercommand if chip.supercommand else
                Command.make(chip.__class__.__name__, "No descrpition provided.")
            )
        return super().use(chip)

    @Handle(enums.tcode.Ready)
    async def _registerCommands(self, _):

        t_RegdCommands = dict[str, api.ApplicationCommand]
        t_GuildRegdCommands = dict[api.Snowflake, t_RegdCommands]
        def dictify(ls: list[api.ApplicationCommand]):
            return {command.name: command for command in ls}

        regdGlobally: t_RegdCommands = dictify(await self.http.getGlobalCommands())

        regdGuildly: t_GuildRegdCommands = {}
        for guildID in self.guildIDs:
            regdGuildly[guildID] = dictify(await self.http.getGuildCommands(guildID))

        for pendingCommand in Command.get(self).values():
            if self.TEST_IN: pendingCommand.guildID = api.Snowflake(self.TEST_IN)
            await self._processPendingCommand(pendingCommand, regdGlobally, regdGuildly)

        for remainingCommand in regdGlobally.values():
            self.printCommand(f"deleting `{remainingCommand.name}`")
            await self.http.deleteCommand(remainingCommand.id)

        for guildID in regdGuildly:
            for remainingGuildCommand in regdGuildly[guildID].values():
                self.printCommand(f"deleting `{remainingGuildCommand.name}` from guild {remainingGuildCommand.guild_id}")
                await self.http.deleteGuildCommand(guildID, remainingGuildCommand.id)

    async def _processPendingCommand(self,
        pendingCommand: make.Command,
        regdGlobally: dict[str,
            api.ApplicationCommand],
        regdGuildly: dict[api.Snowflake,
            dict[str,
                api.ApplicationCommand]]
    ):
        if pendingCommand.guildID:
            if not pendingCommand.guildID in regdGuildly:
                self.printCommand(f"creating `{pendingCommand.name}` in guild {pendingCommand.guildID}")
                return await self.http.postGuildCommand(pendingCommand.guildID, pendingCommand)

            regdCommands = regdGuildly[pendingCommand.guildID]
            if not pendingCommand.name in regdCommands:
                self.printCommand(f"creating `{pendingCommand.name}` in guild {pendingCommand.guildID}")
                return await self.http.postGuildCommand(pendingCommand.guildID, pendingCommand)

            regdCommand = regdCommands.pop(pendingCommand.name)
            if pendingCommand.eq(regdCommand):
                self.printCommand(f"matched  `{pendingCommand.name}` in guild {pendingCommand.guildID}")
                return

            self.printCommand(f"patching `{pendingCommand.name}` in guild {pendingCommand.guildID}")
            return await self.http.patchGuildCommand(pendingCommand.guildID, regdCommand.id, pendingCommand)

        if not pendingCommand.name in regdGlobally:
            self.printCommand(f"creating `{pendingCommand.name}`")
            return await self.http.postCommand(pendingCommand)

        regdCommand = regdGlobally.pop(pendingCommand.name)
        if pendingCommand.eq(regdCommand):
            self.printCommand(f"matched  `{pendingCommand.name}`")
            return

        self.printCommand(f"patching `{pendingCommand.name}`")
        return await self.http.patchCommand(regdCommand.id, pendingCommand)

    @Handle(api.tcode.InteractionCreate)
    async def _interaction(self, interaction: api.Interaction):
        if interaction.data:
            ixn = Ixn(interaction, self.http)
            if interaction.type == enums.InteractionEventTypes.ApplicationCommand:
                match interaction.data.type:
                    case enums.ApplicationCommandTypes.ChatInput:
                        await self._chatInput(ixn, interaction.data)

    async def _chatInput(self, ixn: Ixn, data: api.InteractionData):
        if not data.name: raise AttributeError()
        commands = Command.get(self)
        params = {}
        if data.options:
            for option in data.options:
                params[option.name] = self._getParamsForTR(commands[data.name], option, data.resolved)
        await commands[data.name].call(self, ixn, **params)

    def _getParamsForTR(self, command: Command, option: api.InteractionCommandDataOption, resolved: api.InteractionCommandDataResolved | None):
        hint = command.getOption(option.name)
        if not hint: raise ValueError(f"Function for Learn {command.reference()} got unexpected option {option.name}")
        param = option.value
        # We have to fix up the Member objects to include the users that have been resolved alongside them.
        if resolved and resolved.members:
            if not resolved.users: resolved.users = {}
            for memberID, member in resolved.members.items():
                if memberID in resolved.users:
                    member.user = resolved.users[memberID]

        t_Resolved = TypeVar("t_Resolved", bound=api.Disc)
        def _cast(resolvedObjects: dict[api.Snowflake, t_Resolved] | None):
            if resolvedObjects is None: raise AttributeError()
            id_ = api.Snowflake(option.value)
            if id_ in resolvedObjects:
                return resolvedObjects[id_]
            else:
                raise ValueError(f"Function for Learn `{command.reference()}` couldn't find a resolved object for option {option.name}")

        match hint.type:
            case enums.CommandOptionTypes.User:
                param = _cast(resolved.users if resolved else None)
            case enums.CommandOptionTypes.Member:
                param = _cast(resolved.members if resolved else None)
            case enums.CommandOptionTypes.Role:
                param = _cast(resolved.roles if resolved else None)
            case enums.CommandOptionTypes.Channel:
                param = _cast(resolved.channels if resolved else None)
            case enums.CommandOptionTypes.Mentionable:
                param = api.Snowflake(param)
            case enums.CommandOptionTypes.SubCommand | enums.CommandOptionTypes.SubCommandGroup:
                param = command.getOption(option.name)
                if not isinstance(param, Machine): raise ValueError()
        return param
