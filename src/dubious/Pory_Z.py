
import re
from typing import ClassVar

from dubious.discord import api, enums
from dubious.GuildStructure import Item, Many, One, Structure
from dubious.Interaction import Ixn
from dubious.Machines import Command, Handle, Option, Subcommand
from dubious.Pory2 import Pory2

pat_ID = re.compile(r"<[#@]+:?(\d{18})>")

class Pory_Z(Pory2):

    Channels: ClassVar[type[Structure]]
    Roles: ClassVar[type[Structure]]

    async def _getID(self, ixn: Ixn, value: str):
        match = pat_ID.match(value)
        if not match:
            await ixn.respond(f"Couldn't find any IDs in \"{str}\".")
            return None
        return api.Snowflake(match.group(1))
    async def _getIDs(self, ixn: Ixn, value: str):
        matches = [api.Snowflake(match) for match in pat_ID.findall(value)]
        if not matches:
            await ixn.respond(f"Couldn't find any IDs in \"{str}\".")
        return matches

    @Subcommand.new("set", f"Sets the ID of an item.", options=[
        Option("value", "The ID to assign to the item.", enums.CommandOptionTypes.String)
    ])
    async def _set(self, ixn: Ixn, gid: api.Snowflake, item: One, structure: Structure, value: str):
        id = await self._getID(ixn, value)
        if not id: return
        structure.set(gid, item, id)
        await ixn.respond(f"Set the ID of {item.name} to {id}.")

    @Subcommand.new("unset", f"Removes the ID of an item.")
    async def _unset(self, ixn: Ixn, gid: api.Snowflake, item: One, structure: Structure):
        structure.unset(gid, item)
        await ixn.respond(f"Set the ID of {item.name} to None.")

    @Subcommand.new("add", f"Adds IDs to an item.", options=[
        Option("value", "The ID to add to the item.", enums.CommandOptionTypes.String)
    ])
    async def _add(self, ixn: Ixn, gid: api.Snowflake, item: Many, structure: Structure, value: str):
        ids = await self._getIDs(ixn, value)
        if not ids: return
        for id in ids: structure.add(gid, item, id)
        await ixn.respond(f"Added IDs {ids} to {item.name}.")

    @Subcommand.new("rm", f"Removes IDs from an item.", options=[
        Option("value", "The ID to remove from the item.", enums.CommandOptionTypes.String)
    ])
    async def _rm(self, ixn: Ixn, gid: api.Snowflake, item: Many, structure: Structure, value: str):
        ids = await self._getIDs(ixn, value)
        if not ids: return
        for id in ids: structure.rm(gid, item, id)
        await ixn.respond(f"Removed IDs {ids} from {item.name}.")

    @Subcommand.new("clear", f"Removes all IDs from an item.")
    async def _clear(self, ixn: Ixn, gid: api.Snowflake, item: Many, structure: Structure):
        structure.clear(gid, item)
        await ixn.respond(f"Removed all IDs from {item.name}.")

    @Handle(enums.tcode.Ready)
    async def configure(self, _):
        self._channels = self.Channels(self.guildIDs)
        self._roles = self.Roles(self.guildIDs)

        for item in self.Channels.getItems():
            self._makeCommand(item, self._channels)

        for item in self.Roles.getItems():
            self._makeCommand(item, self._channels)

    @Command.new("config", "Configure the ID or IDs stored under a name for this guild.")
    async def config(self, ixn: Ixn):
        if not ixn.guildID:
            await ixn.respond(f"Can't set the ID of any items outside of a guild.")
            return
        return ixn.guildID

    def _makeCommand(self, item: Item, structure: Structure):

        @Subcommand.new(item.name, f"Alters the {'ID' if isinstance(item, One) else 'IDs'} stored in {item.name}.")
        async def alter(_, ixn: Ixn, gid: api.Snowflake):
            return gid, item, structure

        self.config.subcommand(alter)

        if isinstance(item, One):
            alter.subcommand(self._set)
            alter.subcommand(self._unset)
        else:
            alter.subcommand(self._add)
            alter.subcommand(self._rm)
            alter.subcommand(self._clear)

    def getChannel(self, guildID: api.Snowflake, which: Item):
        return self._channels.get(guildID, {}).get(which.name)

    def getRole(self, guildID: api.Snowflake, which: Item):
        return self._roles.get(guildID, {}).get(which.name)
