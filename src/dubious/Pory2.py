
import asyncio
import sys
import traceback
from typing import Any, Callable, ClassVar, Coroutine, TypeVar
from typing_extensions import Self

from websockets import client
from websockets import exceptions as wsExceptions

from dubious.discord import api, enums, make, rest
from dubious.Pory import HalfRegister, Handle, Pory

t_CallbackDisc = TypeVar("t_CallbackDisc")
t_CallbackPory2 = TypeVar("t_CallbackPory2", bound="Pory2")

class Dumps:
    def dump(self):
        pass

class Learn(HalfRegister[t_CallbackPory2, t_CallbackDisc], Dumps):
    callback: Callable[[t_CallbackPory2, t_CallbackDisc], Coroutine[Any, Any, Any]]
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
        return make.Command(
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
        return make.CommandOption(
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
        return make.CommandOptionChoice(
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
    _joinUrl: str

    uri: ClassVar = "wss://gateway.discord.gg/?v=9&encoding=json"
    doWelcome: ClassVar = True
    doAlertUnhandledEvents: ClassVar = True

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
        self._ws = await client.connect(self.uri)

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
                self._ws = await client.connect(self.uri)
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
            if isinstance(inner, dict):
                if self.doAlertUnhandledEvents:
                    print(f"unhandled event {code}")
                continue
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
        if self.doWelcome:
            print(f"{self.user.username} is ready!\nAdd this bot to a server using the following link:\nhttps://discord.com/api/oauth2/authorize?client_id={self.user.id}&permissions=0&scope=bot%20applications.commands")
    
    @Handle(api.tcode.Reconnect)
    async def _doResume(self, canReconnect: bool):
        if not canReconnect: return
        await self._q.put(api.Payload(
            op = enums.opcode.Resume,
            t=None,
            s=self._last,
            d=make.Resume(
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
            d = make.Identify(
                token=self._token,
                intents=self._intents,
                properties={
                    "$os": sys.platform,
                    "$browser": "dubiousdiscord",
                    "$device": "dubiousdiscord"
                }
            )
        ))


class Ixn:
    _ixn: api.Interaction
    _http: rest.Http

    def __init__(self, ixn: api.Interaction, http: rest.Http):
        self._ixn = ixn
        self._http = http

    t_Response = make.Response | make.CallbackData | str
    
    def _castData(self, response: t_Response):
        if isinstance(response, str):
            return  make.RMessage(content=response)
        elif isinstance(response, make.Response):
            return response.data
        return response
    
    def _castResponse(self, response: t_Response):
        response = self._castData(response)
        return make.Response(
            type=enums.InteractionResponseTypes.CmdMessage,
            data=response
        )
    
    async def _makeMessage(self, response: t_Response, using: Callable[[make.Response], Coroutine[Any, Any, api.Message | None]], silent: bool, private: bool):
        if not silent:
            response = self._castResponse(response)
            return await using(response)
        else:
            response = self._castData(response)
            msg = await self._makeMessage(make.RMessage(content=enums.Empty), using, silent, private)
            if not msg:
                await self.edit(response)
            else:
                await self.edit(response, msg.id)
    
    async def edit(self, response: t_Response, id: api.Snowflake | rest.t_Original=enums.IxnOriginal):
        response = self._castData(response)
        return await self._http.patchInteractionMessage(self._ixn.token, id, response)

    async def respond(self, response: t_Response, *, silent=False, private=False):
        return await self._makeMessage(
            response,
            lambda res: self._http.postInteractionResponse(self._ixn.id, self._ixn.token, res),
            silent, private
        )
    
    async def followup(self, response: t_Response, *, silent=False, private=False):
        return await self._makeMessage(
            response,
            lambda res: self._http.postInteractionFollowup(self._ixn.token, res),
            silent, private
        )


class Pory2(Upgrade):
    name: ClassVar[str]
    _commands: dict[str, Learn[Self, Ixn]]

    doPrintCommands: ClassVar = True

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
            if self.doPrintCommands: print(f"deleting {remainingCommand.name}")
            await self.http.deleteCommand(remainingCommand.id)
        for guildID in regdGuildly:
            for remainingGuildCommand in regdGuildly[guildID].values():
                if self.doPrintCommands: print(f"deleting {remainingGuildCommand.name} from guild {remainingGuildCommand.guild_id}")
                await self.http.deleteGuildCommand(guildID, remainingGuildCommand.id)
    
    async def _processPendingCommand(self,
        pendingCommand: make.Command,
        regdGlobally: dict[str, api.ApplicationCommand],
        regdGuildly: dict[api.Snowflake, dict[str, api.ApplicationCommand]]
    ):
        if pendingCommand.guildID:
            if not pendingCommand.guildID in regdGuildly:
                if self.doPrintCommands: print(f"creating `{pendingCommand.name}` in guild {pendingCommand.guildID}")
                return await self.http.postGuildCommand(pendingCommand.guildID, pendingCommand)
            else:
                regdCommands = regdGuildly[pendingCommand.guildID]
                if not pendingCommand.name in regdCommands:
                    if self.doPrintCommands: print(f"creating `{pendingCommand.name}` in guild {pendingCommand.guildID}")
                    return await self.http.postGuildCommand(pendingCommand.guildID, pendingCommand)
                else:
                    regdCommand = regdCommands.pop(pendingCommand.name)
                    if self.doPrintCommands: print(f"patching `{pendingCommand.name}` in guild {pendingCommand.guildID}")
                    return await self.http.patchGuildCommand(pendingCommand.guildID, regdCommand.id, pendingCommand)
        else:
            if not pendingCommand.name in regdGlobally:
                if self.doPrintCommands: print(f"creating `{pendingCommand.name}`")
                return await self.http.postCommand(pendingCommand)
            else:
                regdCommand = regdGlobally.pop(pendingCommand.name)
                if self.doPrintCommands: print(f"patching `{pendingCommand.name}`")
                return await self.http.patchCommand(regdCommand.id, pendingCommand)
    
    @Handle(api.tcode.InteractionCreate)
    async def _handleInteraction(self, data: api.Interaction):
        if data.data:
            ixn = Ixn(data, self.http)
            if data.data.name and data.data.name in self._commands:
                await self._commands[data.data.name].callback(self, ixn)
