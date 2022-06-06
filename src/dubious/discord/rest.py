
import asyncio
from enum import Enum
from typing import (Any, ClassVar, Dict, Generic, List, Literal, TypeVar,
                    overload)

import aiohttp
from aiohttp import hdrs
from dubious.discord import api, make
from pydantic import BaseModel

from dubious.discord.enums import IxnOriginal


def removeNonDicts(l: List) -> List[Dict]:
    i = 0
    while i < len(l):
        c = l[i]
        if not isinstance(c, dict):
            l.pop(i)
        else:
            i += 1
    return l

t_IDable = TypeVar("t_IDable", bound=api.IDable)
class Cache(Generic[t_IDable], BaseModel):
    cast: type[t_IDable]
    maxSize: int = 1000
    items: Dict[api.Snowflake, t_IDable] = {}
    order: List[api.Snowflake] = []

    def _add(self, item: t_IDable):
        if item.id in self.items:
            return self.items[item.id]
        if len(self.items) + 1 > self.maxSize:
            self.items.pop(self.order[0])
            self.order.pop(0)
        self.items[item.id] = item
        self.order.append(item.id)
        return item
    
    def add(self, j: dict | list):
        if isinstance(j, list):
            items = [self.cast.parse_obj(item) for item in removeNonDicts(j)]
            for item in items:
                self._add(item)
        item = self.cast.parse_obj(j)
        item = self._add(item)
        return item
    
    def get(self, oID: api.Snowflake):
        return self.items.get(oID)

class HTTPError(Exception):
    """ Something went wrong with an HTTP request."""
    def __init__(self, url: str, error: api.Error, payload: api.Disc | None):
        self.code = error.code
        self.message = error.message
        self.errors = error.errors
        self.payload = payload
        super().__init__(f"in {payload.__class__.__name__}:\n{self.payload.debug(ignoreNested=False) if self.payload else None}\n\nin {url}:\n  {self.code}: {self.message}\n{self.formatErrors(self.errors, tab=2)}")

    def formatErrors(self, errors: api.RequestError | api.ObjectError | api.ArrayError | None, tab=0):
        tabulation = '  '*tab
        if errors is None:
            return f"{tabulation}No message"
        elif isinstance(errors, api.RequestError):
            return "\n".join([f"{tabulation}{error.code}: {error.message}" for error in errors.errors])
        elif isinstance(errors, api.ObjectError):
            return "\n".join([f"{tabulation}{fieldName}:\n{self.formatErrors(value, tab+1)}" for fieldName, value in errors.errors.items()])
        else:
            return "\n".join([f"{tabulation}{num}:\n{self.formatErrors(value, tab+1)}" for num, value in enumerate(errors.items)])

class ResponseError(Exception):
    def __init__(self, method: str, url: str, expected: type):
        super().__init__(f"{method} {url}: Expected {expected}")

class BuildURL:
    def __init__(self, baseUrl: str, aID: api.Snowflake) -> None:
        self.baseUrl = baseUrl
        self.id = aID

    def commands(self, guildID: api.Snowflake | None, commandID: api.Snowflake | None):
        applications = f"/applications/{self.id}"
        guilds = f"/guilds/{guildID}" if guildID else ""
        commands = f"/commands/{commandID}" if commandID else "/commands"
        return self.baseUrl + applications + guilds + commands

    def interactions(self, ixnID: api.Snowflake | None, ixnToken: str):
        interactions = f"/interactions/{ixnID}/{ixnToken}/callback"
        return self.baseUrl + interactions

    def guilds(self, guildID: api.Snowflake | None):
        guilds = f"/guilds/{guildID}"
        return self.baseUrl + guilds

    def channels(self, channelID: api.Snowflake | None):
        channels = f"/channels/{channelID}"
        return self.baseUrl + channels

    def messages(self, channelID: api.Snowflake, messageID: api.Snowflake | None | Literal["bulk-delete"]):
        channels = f"/channels/{channelID}"
        messages = f"/messages/{messageID}" if messageID else f"/messages"
        return self.baseUrl + channels + messages

    def webhooks(self, webhookID: api.Snowflake | None, webhookToken: str | None):
        webhooks = f"/webhooks/"
        wid = f"/{webhookID}" if webhookID else ""
        token = f"/{webhookToken}" if webhookID and webhookToken else ""
        return self.baseUrl + webhooks + wid + token

    def webhookMessages(self, webhookID: api.Snowflake, webhookToken: str, messageID: api.Snowflake | None | Literal["@original"]):
        webhooks = f"/webhooks/{webhookID}/{webhookToken}"
        messages = f"/messages/{messageID}" if messageID else ""
        return self.baseUrl + webhooks + messages

class Expects(int, Enum):
    none = 0
    single = 1
    multiple = 2

t_Expects = Literal[Expects.none] | Literal[Expects.single] | Literal[Expects.multiple]
t_Original = Literal["@original"]

class Http:
    token: str
    session: aiohttp.ClientSession

    caches: Dict[type[api.IDable], Cache] = {}

    version: ClassVar = "v9"
    baseUrl: ClassVar = f"https://discord.com/api/{version}"
    url: BuildURL

    def __init__(self, appID: api.Snowflake, appToken: str):
        self.id = appID
        self.token = appToken
        self.session = aiohttp.ClientSession()

        self.url = BuildURL(self.baseUrl, self.id)

        for typ in [
            api.ApplicationCommand,
            api.Guild,
            api.Channel,
            api.Message,
            api.Webhook
        ]: self._addCache(typ)

        self.auth = {
            "Authorization": f"Bot {self.token}"
        }

    def _addCache(self, typ: type[api.IDable]):
        self.caches[typ] = Cache(cast=typ)

    async def close(self):
        await self.session.close()

    async def handleRes(self, res: aiohttp.ClientResponse):
        if not res.status in range(200, 300):
            error = api.Error(**await res.json())
            if error.retry_after is not None:
                await asyncio.sleep(error.retry_after)
                return False # rate limited

            return error

        if not await res.text():
            return None

        got = await res.json()
        return got

    @overload
    async def request(self, method: str, typ: type[t_IDable], expects: Literal[Expects.none], url: str, payload: make.Make | None=None, **params: Any) -> None: ...
    @overload
    async def request(self, method: str, typ: type[t_IDable], expects: Literal[Expects.single], url: str, payload: make.Make | None=None, **params: Any) -> t_IDable: ...
    @overload
    async def request(self, method: str, typ: type[t_IDable], expects: Literal[Expects.multiple], url: str, payload: make.Make | None=None, **params: Any) -> List[t_IDable]: ...
    
    async def request(self, method: str, typ: type[t_IDable], expects: t_Expects, url: str, payload: make.Make | None=None, **params: Any) -> None | t_IDable | List[t_IDable]:
        headers: Dict[str, Dict[str, Any] | str] = {"headers": self.auth}
        if payload: headers["json"] = payload.dict()
        if params: headers["params"] = params

        async with self.session.request(method, url, **headers) as res:
            ret = await self.handleRes(res)

            if ret == False: # rate limited (waiting happens in the handleRes)
                return await self.request(method, typ, expects, url, payload, **params)
            if isinstance(ret, api.Error):
                raise HTTPError(url, ret, payload)

            if expects == Expects.none:
                if ret is not None: raise ResponseError(method, url, type(None))
                return ret
            if expects == Expects.single:
                if not isinstance(ret, dict): raise ResponseError(method, url, typ)
                return typ.parse_obj(ret)
            if expects == Expects.multiple:
                if not isinstance(ret, list): raise ResponseError(method, url, list[typ])
                return [typ.parse_obj(item) for item in ret]

            raise ResponseError(method, url, Any)

    async def getGlobalCommands(self):
        return await self.request(
            hdrs.METH_GET, api.ApplicationCommand, Expects.multiple,
            self.url.commands(None, None) )
    async def getGuildCommands(self, guildID: api.Snowflake):
        return await self.request(
            hdrs.METH_GET, api.ApplicationCommand, Expects.multiple,
            self.url.commands(guildID, None) )
    async def getCommand(self, commandID: api.Snowflake):
        return await self.request(
            hdrs.METH_GET, api.ApplicationCommand, Expects.single,
            self.url.commands(None, commandID) )
    async def getGuildCommand(self, guildID: api.Snowflake, commandID: api.Snowflake):
        return await self.request(
            hdrs.METH_GET, api.ApplicationCommand, Expects.single,
            self.url.commands(guildID, commandID) )
    async def postCommand(self, command: make.Command):
        return await self.request(
            hdrs.METH_POST, api.ApplicationCommand, Expects.single,
            self.url.commands(None, None), command)
    async def postGuildCommand(self, guildID: api.Snowflake, command: make.Command):
        return await self.request(
            hdrs.METH_POST, api.ApplicationCommand, Expects.single,
            self.url.commands(guildID, None), command)
    async def patchCommand(self, commandID: api.Snowflake, command: make.Command):
        return await self.request(
            hdrs.METH_PATCH, api.ApplicationCommand, Expects.single,
            self.url.commands(None, commandID), command)
    async def patchGuildCommand(self, guildID: api.Snowflake, commandID: api.Snowflake, command: make.Command):
        return await self.request(
            hdrs.METH_PATCH, api.ApplicationCommand, Expects.single,
            self.url.commands(guildID, commandID), command)
    async def deleteCommand(self, commandID: api.Snowflake):
        return await self.request(
            hdrs.METH_DELETE, api.ApplicationCommand, Expects.none,
            self.url.commands(None, commandID))
    async def deleteGuildCommand(self, guildID: api.Snowflake, commandID: api.Snowflake):
        return await self.request(
            hdrs.METH_DELETE, api.ApplicationCommand, Expects.none,
            self.url.commands(guildID, commandID))

    async def getMessage(self, channelID: api.Snowflake, messageID: api.Snowflake):
        return await self.request(
            hdrs.METH_GET, api.Message, Expects.single,
            self.url.messages(channelID, messageID) )
    async def getMessages(self, channelID: api.Snowflake, limit: int=100):
        assert limit > 0 and limit <= 100
        return await self.request(
            hdrs.METH_GET, api.Message, Expects.multiple,
            self.url.messages(channelID, None), limit=limit)
    async def postMessage(self, channelID: api.Snowflake, message: make.RMessage):
        return await self.request(
            hdrs.METH_POST, api.Message, Expects.single,
            self.url.messages(channelID, None), message)
    async def patchMessage(self, channelID: api.Snowflake, messageID: api.Snowflake, message: make.RMessage):
        return await self.request(
            hdrs.METH_PATCH, api.Message, Expects.single,
            self.url.messages(channelID, messageID), message)
    async def deleteMessage(self, channelID: api.Snowflake, messageID: api.Snowflake):
        return await self.request(
            hdrs.METH_DELETE, api.Message, Expects.single,
            self.url.messages(channelID, messageID) )
    async def deleteMessages(self, channelID: api.Snowflake, messageIDs: List[api.Snowflake]):
        assert len(messageIDs) <= 100
        return await self.request(
            hdrs.METH_POST, api.Message, Expects.multiple,
            self.url.messages(channelID, "bulk-delete"), messages=messageIDs)

    async def postInteractionResponse(self, interactionID: api.Snowflake, token: str, response: make.Response):
        return await self.request(
            hdrs.METH_POST, api.Message, Expects.none,
            self.url.interactions(interactionID, token), response)
    async def postInteractionFollowup(self, token: str, followup: make.CallbackData):
        return await self.request(
            hdrs.METH_POST, api.Message, Expects.single,
            self.url.webhookMessages(self.id, token, None), followup)
    async def getInteractionMessage(self, token: str, messageID: api.Snowflake | None | t_Original=IxnOriginal):
        return await self.request(
            hdrs.METH_GET, api.Message, Expects.single,
            self.url.webhookMessages(self.id, token, messageID) )
    async def patchInteractionMessage(self, token: str, messageID: api.Snowflake | t_Original, message: make.CallbackData):
        return await self.request(
            hdrs.METH_PATCH, api.Message, Expects.single,
            self.url.webhookMessages(self.id, token, messageID), message)
    async def deleteInteractionMessage(self, token: str, messageID: api.Snowflake | t_Original=IxnOriginal):
        return await self.request(
            hdrs.METH_DELETE, api.Message, Expects.none,
            self.url.webhookMessages(self.id, token, messageID))

    async def getGuild(self, id: api.Snowflake):
        return await self.request(
            hdrs.METH_GET, api.Guild, Expects.single,
            self.url.guilds(id) )

    async def getChannel(self, id: api.Snowflake):
        return await self.request(
            hdrs.METH_GET, api.Channel, Expects.single,
            self.url.channels(id) )
