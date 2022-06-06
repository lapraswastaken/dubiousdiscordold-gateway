
import abc
import re
from typing import ClassVar, TypeGuard

from dubious.discord import api, enums
from dubious.GuildStructure import Item, Many, ModStructure, One, Structure
from dubious.Interaction import GuildIxn, Ixn
from dubious.Machines import Check, Command, FailedCheck, Handle, Option, Subcommand
from dubious.Pory2 import Pory2

pat_ID = re.compile(r"<[#@&]+:?(\d{18})>")

class Pory_Z(Pory2, abc.ABC):

    @Handle(enums.tcode.Ready)
    async def configure(self, _):
        self._channels = self.Channels(self.guildIDs)
        self._roles = self.Roles(self.guildIDs)

        for item in self.Channels.getItems():
            self._assembleConfig(item, self._channels)

        for item in self.Roles.getItems():
            self._assembleConfig(item, self._roles)

    Channels: ClassVar[type[Structure]]
    Roles: ClassVar[type[ModStructure]]

    async def _getID(self, ixn: Ixn, value: str):
        match = pat_ID.match(value)
        if not match:
            await ixn.respond(f"Couldn't find any IDs in \"{value}\".")
            return None
        return api.Snowflake(match.group(1))

    async def _getIDs(self, ixn: Ixn, value: str):
        matches = [api.Snowflake(match) for match in pat_ID.findall(value)]
        if not matches:
            await ixn.respond(f"Couldn't find any IDs in \"{value}\".")
        return matches

    def getChannel(self, gid: api.Snowflake, which: Item):
        """ Gets a channel ID / channel IDs from an item in the `self.Channels`
            structure assigned to a specific guild. """

        return self._channels.get(gid, {}).get(which.name)

    def getRole(self, gid: api.Snowflake, which: Item):
        """ Gets a role ID / role IDs from an item in the `self.Roles` structure
            assigned to a specific guild. """

        return self._roles.get(gid, {}).get(which.name)

    def getMemberHasRoles(self, gid: api.Snowflake, which: Item, member: api.Member):
        """ Returns whether or not the member has a role in an Item for the
            given guild. """

        roles = self.getRole(gid, which)
        if isinstance(roles, list):
            return any([role in roles for role in member.roles])
        else:
            return roles in member.roles

    @Check()
    def checkIsInGuild(self, ixn: Ixn | GuildIxn):
        if not isinstance(ixn, GuildIxn):
            return "You can't use this command outside of a guild."
        return True

    @Check().andCheck(checkIsInGuild)
    async def checkIsMemberGuildOwner(self, ixn: GuildIxn):
        if not ixn.member.user:
            return "This interaction object's member isn't tied to a user. How tf"
        if not (await ixn.guild()).owner_id == ixn.member.user.id:
            return "Only the guild owner can use this command."
        return True

    @Check().andCheck(checkIsInGuild)
    async def checkIsMod(self, ixn: GuildIxn):
        if await self.checkIsMemberGuildOwner(ixn) is True:
            return True

        if not self.getRole(ixn.guildID, self.Roles.getModRoleItem()):
            return "This guild has no moderator role set up yet. Ask the server owner to configure a role as the moderator role."
        elif self.getMemberHasRoles(ixn.guildID, self.Roles.getModRoleItem(), ixn.member):
            return True
        return "Only members with the moderator role can use this command."

    @Command.new("config",
        "Configure the ID or IDs stored under a name for this guild."
    ).andCheck(
        checkIsMod
    )
    async def config(self, ixn: Ixn):
        pass

    def _assembleConfig(self, item: Item, structure: Structure):
        """ Builds the `config` command to be registered in a server.

            Adds a subcommand for each type of ID, and depending on if it's One
            or Many, adds the respective subcommands to alter that ID. """

        # We create the "alter" subcommand dynamically with the given item's
        #  name, so we can't define it on the class.
        @Subcommand.new(item.name,
            f"Alters the {'ID' if isinstance(item, One) else 'IDs'} stored in {item.name}."
        )
        async def _alter(_, __: GuildIxn):
            return item, structure
        alter = Subcommand.get(_alter)
        if isinstance(structure, ModStructure) and structure.getModRoleItem() == item:
            alter.andCheck(self.checkIsMemberGuildOwner)

        Command.get(self.config).subcommand(alter)
        alter.subcommand(Subcommand.get(self._get))

        if isinstance(item, One):
            alter.subcommand(Subcommand.get(self._set))
            alter.subcommand(Subcommand.get(self._unset))
        else:
            alter.subcommand(Subcommand.get(self._add))
            alter.subcommand(Subcommand.get(self._rm))
            alter.subcommand(Subcommand.get(self._clear))

    #####
    # ID Manipulation Subcommand defs
    #####

    @Subcommand.new("get",
        f"Gets the ID or IDs set for this item."
    )
    async def _get(self, ixn: GuildIxn, item: One | Many, structure: Structure):
        gotten = structure.getFromItem(ixn.guildID, item)
        await ixn.respond(f"`{item.name}`: `{gotten}`")

    @Subcommand.new("set",
        f"Sets the ID of an item.",
        options=[
            Option("value", "The ID to assign to the item.", enums.CommandOptionTypes.String)
        ]
    )
    async def _set(self, ixn: GuildIxn, item: One, structure: Structure, value: str):
        id = await self._getID(ixn, value)
        if not id: return
        structure.set(ixn.guildID, item, id)
        await ixn.respond(f"Set the ID of `{item.name}` to `{id}`.")

    @Subcommand.new("unset",
        f"Removes the ID of an item."
    )
    async def _unset(self, ixn: GuildIxn, item: One, structure: Structure):
        structure.unset(ixn.guildID, item)
        await ixn.respond(f"Set the ID of `{item.name}` to `None`.")

    @Subcommand.new("add",
        f"Adds IDs to an item.",
        options=[
            Option("value", "The ID to add to the item.", enums.CommandOptionTypes.String)
        ]
    )
    async def _add(self, ixn: GuildIxn, item: Many, structure: Structure, value: str):
        ids = await self._getIDs(ixn, value)
        if not ids: return
        for id in ids: structure.add(ixn.guildID, item, id)
        await ixn.respond(f"Added IDs `{ids}` to `{item.name}`.")

    @Subcommand.new("rm",
        f"Removes IDs from an item.",
        options=[
            Option("value", "The ID to remove from the item.", enums.CommandOptionTypes.String)
        ]
    )
    async def _rm(self, ixn: GuildIxn, item: Many, structure: Structure, value: str):
        ids = await self._getIDs(ixn, value)
        if not ids: return
        for id in ids: structure.rm(ixn.guildID, item, id)
        await ixn.respond(f"Removed IDs `{ids}` from `{item.name}`.")

    @Subcommand.new("clear",
        f"Removes all IDs from an item."
    )
    async def _clear(self, ixn: GuildIxn, item: Many, structure: Structure):
        structure.clear(ixn.guildID, item)
        await ixn.respond(f"Removed all IDs from `{item.name}`.")
