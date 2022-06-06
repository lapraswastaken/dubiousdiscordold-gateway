
from typing import Any, Callable, Coroutine
from dubious.discord import api, enums, make, rest

def makeIxn(ixn: api.Interaction, http: rest.Http):
    if ixn.guild_id: return GuildIxn(ixn, http)
    return Ixn(ixn, http)

class Ixn:
    """ Holds methods and relevant information about an `api.Interaction` object
        recieved from Discord. """


    _ixn: api.Interaction
    _http: rest.Http

    user: api.User

    def __init__(self, ixn: api.Interaction, http: rest.Http):
        self._ixn = ixn
        self._http = http

        self.user = ixn.member.user if ixn.member else ixn.user # type: ignore

    t_Response = make.Response | make.CallbackData | str

    def _castData(self, response: t_Response):
        if isinstance(response, str):
            return make.RMessage(content=response)
        elif isinstance(response, make.Response):
            return response.data
        return response

    def _castResponse(self, response: t_Response):
        response = self._castData(response)
        return make.Response(
            type=enums.InteractionResponseTypes.CmdMessage,
            data=response
        )

    async def _makeMessage(self,
        response: t_Response,
        using: Callable[
            [make.Response],
                Coroutine[Any, Any, api.Message | None]],
        silent: bool,
        private: bool,
    ):
        if not silent:
            response = self._castResponse(response)
            return await using(response)
        else:
            response = self._castData(response)
            empty = make.RMessage(content=enums.Empty)
            msg = await self._makeMessage(empty, using, False, private)
            if not msg:
                await self.edit(response)
            else:
                await self.edit(response, msg.id)

    async def edit(self, response: t_Response, id: api.Snowflake | rest.t_Original=enums.IxnOriginal):
        """ Edits a pre-existing response to the bound `api.Interaction`. """

        response = self._castData(response)
        return await self._http.patchInteractionMessage(self._ixn.token, id, response)

    async def respond(self, response: t_Response, *, silent=False, private=False):
        """ Creates an initial response to the bound `api.Interaction`. Can only
            be called once per instance. """

        return await self._makeMessage(
            response,
            lambda res: self._http.postInteractionResponse(self._ixn.id, self._ixn.token, res),
            silent, private
        )

    async def followup(self, response: t_Response, *, silent=False, private=False):
        """ Creates a follow-up response to the bound `api.Interaction`. This
            can only be called once `.respond` has been called for the bound
            `api.Interaction`. """

        return await self._makeMessage(
            response,
            lambda res: self._http.postInteractionFollowup(self._ixn.token, res.data),
            silent, private
        )

class GuildIxn(Ixn):
    _guild: api.Guild | None = None
    _channel: api.Channel | None = None

    guildID: api.Snowflake
    channelID: api.Snowflake
    member: api.Member

    async def guild(self):
        if not self._ixn.guild_id: raise AttributeError()
        if not self._guild:
            self._guild = await self._http.getGuild(self._ixn.guild_id)
        return self._guild

    async def channel(self):
        if not self._ixn.channel_id: raise AttributeError()
        if not self._channel:
            self._channel = await self._http.getChannel(self._ixn.channel_id)
        return self._channel

    def __init__(self, ixn: api.Interaction, http: rest.Http):
        super().__init__(ixn, http)
        if not (
            ixn.guild_id and
            ixn.channel_id and
            ixn.member
        ): raise ValueError("Tried to make GuildIxn out of an api.Interaction object that did not originate from a guild.")

        self.guildID = ixn.guild_id
        self.channelID = ixn.channel_id
        self.member = ixn.member
