
import asyncio
import sys
import traceback
from typing import Any, Callable, ClassVar, Coroutine, TypeVar

from websockets import client
from websockets import exceptions as wsExceptions

from dubious.discord import api, enums, rest
from dubious.Pory import HalfRegister, Handle, Pory

t_Callback_Disc = TypeVar("t_Callback_Disc", bound=api.Disc)
t_Callback_Pory2 = TypeVar("t_Callback_Pory2", bound="Pory2")

class Dumps:
    def dump(self):
        pass

class Learn(HalfRegister[t_Callback_Pory2, t_Callback_Disc], Dumps):
    callback: Callable[[t_Callback_Pory2, t_Callback_Disc], Coroutine[Any, Any, Any]]
    # The name that the command will be registered under and called by.
    ident: str
    # The description of what the command does when used.
    description: str

    # A list of arguments for the command.
    options: list["Option"]
    # The ID of the guild in which to register this command.
    guildID: api.Snowflake | None

    # The type of command. Defaults to an application command.
    type: enums.ApplicationCommandTypes

    def __init__(self,
            ident: str,
            description: str,
            options: list["Option"] | None=None,
            guildID: api.Snowflake | int | None=None,
            typ=enums.ApplicationCommandTypes.ChatInput
    ):
        super().__init__(ident)
        self.description = description
        self.options = options if options else []
        self.guildID = api.Snowflake(guildID) if guildID else None
        self.type = typ
    
    def dump(self):
        return api.CCommand(
            name=self.ident,
            type=self.type,
            description=self.description,
            options=[option.dump() for option in self.options] if self.options else None,
            guildID=self.guildID
        )

class Option(Dumps):
    name: str
    description: str
    type: enums.CommandOptionTypes
    required: bool
    choices: list

    def __init__(self, name: str, description: str, typ: enums.CommandOptionTypes, required: bool=False, choices: list | None=None):
        self.name = name
        self.description = description
        self.type = typ
        self.required = required
        self.choices = choices if choices else []

    def dump(self):
        return api.CCommandOption(
            name=self.name,
            description=self.description,
            type=self.type,
            required=self.required,
            choices=[choice.dump() for choice in self.choices] if self.choices else None
        )

class Choice(Dumps):
    name: str
    value: Any

    def __init__(self, name: str, value: Any):
        self.name = name
        self.value = value

    def dump(self):
        return api.CCommandOptionChoice(
            name=self.name,
            value=self.value
        )

class Upgrade(Pory):
    _token: str
    _intents: int
    _q: asyncio.Queue[api.Payload]
    _beat: asyncio.Event
    # Defined after connection
    _ws: client.WebSocketClientProtocol

    # Defined after Hello payload
    _beatrate: int
    _last: int | None

    # Defined after Ready payload
    _session: str
    _user: api.User
    _guildIDs: list[api.Snowflake]
    _http: rest.Http

    _uri: ClassVar = "wss://gateway.discord.gg/?v=9&encoding=json"

    @property
    def token(self): return self._token
    @property
    def q(self): return self._q
    @property
    def user(self): return self._user
    @property
    def guildIDs(self): return self._guildIDs
    @property
    def http(self): return self._http

    def __init__(self):
        super().__init__()

        self._q = asyncio.Queue()
        self._beat = asyncio.Event()

        self._guildIDs = []


    def start(self, token: str, intents: int):
        self._token = token
        self._intents = intents

        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self._pre())
            loop.run_until_complete(self._main())
        except KeyboardInterrupt:
            print("Stopping...")
        finally:
            loop.run_until_complete(self._post())

    async def _pre(self):
        self._ws = await client.connect(self._uri)

    async def _post(self):
        try:
            await self._ws.close()
            await self._http.close()
        except AttributeError:
            pass

    async def _main(self):
        loop = asyncio.get_event_loop()
        while loop.is_running():
            try:
                data = await self._ws.recv()
            except wsExceptions.ConnectionClosedError or asyncio.CancelledError:
                print("Connection was closed")
                break
            except wsExceptions.ConnectionClosedOK:
                self._ws = await client.connect(self._uri)
                await self._doResume.callback(self, True)
                continue
            except:
                traceback.print_exc()
                loop.stop()
                continue
            payload = api.Payload.parse_raw(data)
            code = payload.t if (payload.t is not None) else payload.op
            if not isinstance(code, (enums.opcode, enums.tcode)): continue
            inner = api.cast(payload)
            #print(f"R {code}: {inner if not isinstance(inner, api.Disc) else inner.debug(1, ignoreNested=True)}")
            self._last = payload.s
            if isinstance(inner, dict): continue
            await self._handle(code, inner)
        
    async def _loopSend(self):
        loop = asyncio.get_event_loop()
        while loop.is_running():
            toSend = await self._q.get()
            data = str(toSend.json())
            await self._ws.send(data)
            #print(f"S {toSend.op}: {toSend.d.debug(1, ignoreNested=True) if isinstance(toSend.d, api.Disc) else toSend.d}")

    async def _loopHeartbeat(self):
        loop = asyncio.get_event_loop()
        while loop.is_running():
            await asyncio.sleep(self._beatrate / 1000)
            await self._beat.wait()
            self._beat.clear()
            await self._q.put(api.Payload(
                op=enums.opcode.Heartbeat,
                t=None,
                s=self._last,
                d=None
            ))
        print("Heartbeat ended")

    @Handle(api.opcode.Hello)
    async def _Hello(self, data: api.Hello):
        asyncio.create_task(self._loopSend(), name="sender")

        self._beatrate = data.heartbeat_interval
        asyncio.create_task(self._loopHeartbeat(), name="heartbeat")
        self._beat.set()
        await self._doIdentify()

    @Handle(api.opcode.HeartbeatAck)
    async def _HeartbeatAck(self, _):
        self._beat.set()
        #print("Heartbeat acknowledged")

    @Handle(api.tcode.Ready)
    async def _Ready(self, data: api.Ready):
        self._user = data.user
        self._session = data.session_id
        self._guildIDs = [guild.id for guild in data.guilds]
        self._http = rest.Http(self._user.id, self._token)
    
    @Handle(api.tcode.Reconnect)
    async def _doResume(self, canReconnect: bool):
        if not canReconnect: return
        await self._q.put(api.Payload(
            op = enums.opcode.Resume,
            t=None,
            s=self._last,
            d=api.Resume(
                token = self.token,
                session = self._session,
                seq = self._last
            )
        ))

    async def _doIdentify(self):
        await self._q.put(api.Payload(
            op = enums.opcode.Identify,
            t = None,
            s = self._last,
            d = api.Identify(
                token=self._token,
                intents=self._intents,
                properties={
                    "$os": sys.platform,
                    "$browser": "dubiousdiscord",
                    "$device": "dubiousdiscord"
                }
            )
        ))

class Pory2(Upgrade):
    name: ClassVar[str]
    _commands: dict[str, Learn]

    @property
    def token(self): return super().token
    @property
    def q(self): return super().q
    @property
    def user(self): return super().user
    @property
    def guildIDs(self): return super().guildIDs
    @property
    def http(self): return super().http

    def __init__(self):
        super().__init__()

        self._commands = {}

        for key in dir(self):
            val = getattr(self, key, None)
            
            if isinstance(val, Learn):
                if val.ident in self._commands:
                    raise Exception(f"Command {val.ident} has been created twice.")
                self._commands[val.ident] = val

    @Handle(api.tcode.Ready)
    async def _registerCommands(self, _):
        t_RegdCommands = dict[str, api.ApplicationCommand]
        t_GuildRegdCommands = dict[api.Snowflake, t_RegdCommands]
        def dictify(ls: list[api.ApplicationCommand]):
            return {command.name: command for command in ls}

        regdGlobally: t_RegdCommands = dictify(await self.http.getGlobalCommands())

        regdGuildly: t_GuildRegdCommands = {}
        for guildID in self.guildIDs:
            regdGuildly[guildID] = dictify(await self.http.getGuildCommands(guildID))

        for pendingCommand in self._commands.values():
            createCommand = pendingCommand.dump()
            await self._processPendingCommand(createCommand, regdGlobally, regdGuildly)
        
        for remainingCommand in regdGlobally.values():
            await self.http.deleteCommand(remainingCommand.id)
        for guildID in regdGuildly:
            for remainingGuildCommand in regdGuildly[guildID].values():
                await self.http.deleteGuildCommand(guildID, remainingGuildCommand.id)
    
    async def _processPendingCommand(self,
        pendingCommand: api.CCommand,
        regdGlobally: dict[str, api.ApplicationCommand],
        regdGuildly: dict[api.Snowflake, dict[str, api.ApplicationCommand]]
    ):
        if pendingCommand.guildID:
            if not pendingCommand.guildID in regdGuildly:
                return await self.http.postGuildCommand(pendingCommand.guildID, pendingCommand)
            else:
                regdCommands = regdGuildly[pendingCommand.guildID]
                if not pendingCommand.name in regdCommands:
                    return await self.http.postGuildCommand(pendingCommand.guildID, pendingCommand)
                else:
                    regdCommand = regdCommands.pop(pendingCommand.name)
                    return await self.http.patchGuildCommand(pendingCommand.guildID, regdCommand.id, pendingCommand)
        else:
            if not pendingCommand.name in regdGlobally:
                return await self.http.postCommand(pendingCommand)
            else:
                regdCommand = regdGlobally.pop(pendingCommand.name)
                return await self.http.patchCommand(regdCommand.id, pendingCommand)
        
    
    @Handle(api.tcode.InteractionCreate)
    async def _handleInteraction(self, data: api.Interaction):
        if data.data:
            if data.data.name and data.data.name in self._commands:
                callback = self._commands[data.data.name].callback.__get__(self)
                await callback(data)
