

from typing import ClassVar, TypeVar

from typing_extensions import Self

from dubious.discord import api, enums, make
from dubious.Interaction import Ixn, makeIxn
from dubious.Machines import Check, Command, Handle
from dubious.Pory import Chip, Pory


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

    commands: dict[str, Command]

    def __init_subclass__(cls):
        super().__init_subclass__()
        cls.commands = Command.collectByReference(cls)

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
                Command.new(chip.__class__.__name__, "No descrpition provided.")
            )
        return super().use(chip)

    @Handle(enums.tcode.Ready, order = 5)
    async def _registerCommands(self, _):

        t_RegdCommands = dict[str, api.ApplicationCommand]
        t_GuildRegdCommands = dict[api.Snowflake, t_RegdCommands]
        def dictify(ls: list[api.ApplicationCommand]):
            return {command.name: command for command in ls}

        regdGlobally: t_RegdCommands = dictify(await self.http.getGlobalCommands())

        regdGuildly: t_GuildRegdCommands = {}
        for guildID in self.guildIDs:
            regdGuildly[guildID] = dictify(await self.http.getGuildCommands(guildID))

        for pendingCommand in self.__class__.commands.values():
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
            ixn = makeIxn(interaction, self.http)
            if interaction.type == enums.InteractionEventTypes.ApplicationCommand:
                match interaction.data.type:
                    case enums.ApplicationCommandTypes.ChatInput:
                        await self._chatInput(ixn, interaction.data)

    async def _chatInput(self, ixn: Ixn, data: api.InteractionData):
        if not data.name: raise AttributeError()
        command = self.__class__.commands.get(data.name)
        if not command: raise RuntimeError(f"Tried to run callback for command {data.name} but no callback existed.")
        params = self._processOptions(command, data, data.resolved)
        await command.call(self, ixn, **params)

    def _processOptions(self,
        command: Command,
        data: api.InteractionData | api.InteractionCommandDataOption,
        resolved: api.InteractionCommandDataResolved | None,
        params: dict | None = None
    ):

        if not params: params = {}
        if not data.options: return params
        for option in data.options:
            if option.type in [
                enums.CommandOptionTypes.SubCommand,
                enums.CommandOptionTypes.SubCommandGroup
            ]:
                param = self._processOptions(command, option, resolved, params)
            else:
                param = self._getParamsForCommand(command, option, resolved)
            params[option.name] = param
        return params

    def _getParamsForCommand(self,
        command: Command,
        option: api.InteractionCommandDataOption,
        resolved: api.InteractionCommandDataResolved | None
    ):

        hint = command.getOption(option.name)
        if not hint: raise ValueError(f"Function for Command `{command.reference()}` got unexpected option `{option.name}`")
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
            if not isinstance(option.value, (int, str)):
                raise ValueError(f"Function for command `{command.reference()}` got an unknown option value (`{option.value}`) for option `{option.name}`")
            id_ = api.Snowflake(option.value)
            if id_ in resolvedObjects:
                return resolvedObjects[id_]
            else:
                raise ValueError(f"Function for command `{command.reference()}` couldn't find a resolved object for option `{option.name}`")

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
                if not isinstance(param, (int, str)): raise ValueError()
                param = api.Snowflake(param)
            case enums.CommandOptionTypes.SubCommand | enums.CommandOptionTypes.SubCommandGroup:
                param = option
        return param
