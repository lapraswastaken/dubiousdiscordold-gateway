
import json
from typing import ClassVar, Iterator, Literal, Mapping, overload
from dubious.discord import api


class Item:
    def __init__(self, name: str):
        self.name = name

class One(Item):
    pass

class Many(Item):
    pass

class Structure(Mapping[api.Snowflake, dict[str, api.Snowflake | list[api.Snowflake] | None]]):
    path: ClassVar[str]
    _d: ClassVar[dict[str, Item]]
    d: dict[api.Snowflake, dict[str, api.Snowflake | list[api.Snowflake] | None]]

    def __init_subclass__(cls):
        cls._d = {}
        for name, itemType in cls.__annotations__.items():
            if not issubclass(itemType, Item): continue
            item = itemType(name)
            setattr(cls, name, item)
            cls._d[name] = item

    def __getitem__(self, __k: api.Snowflake) -> dict[str, api.Snowflake | list[api.Snowflake] | None]:
        return self.d.__getitem__(__k)

    def __iter__(self) -> Iterator[str]:
        return self.d.__iter__()

    def __len__(self) -> int:
        return super().__len__()

    def __init__(self, guildIDs: set[api.Snowflake]):

        self.d = {guildID: {
            name: None if isinstance(self._d.get(name), One) else [] for name in self._d
        } for guildID in guildIDs}

        self.load()
        self.write()

    def load(self):
        try:
            with open(self.path, "r") as f:
                j = json.load(f)
        except FileNotFoundError:
            with open(self.path, "x") as f:
                f.write("{}")
            return

        for guildID in self.d:
            if not guildID in j: continue
            for name in self.d[guildID]:
                if not name in j[guildID]: continue
                self.d[guildID][name] = j[guildID][name]

    def write(self):
        with open(self.path, "w") as f:
            json.dump(self.d, f)

    @overload
    def _check(self, gid: api.Snowflake, item: Item, shouldBeMany: Literal[False]=False) -> None: ...
    @overload
    def _check(self, gid: api.Snowflake, item: Item, shouldBeMany: Literal[True]) -> list[api.Snowflake]: ...

    def _check(self, gid: api.Snowflake, item: Item, shouldBeMany: bool=False):
        if not gid in self.d: raise ValueError("Guild ID not found in the registered guilds.")
        if not item.name in self.d[gid]: raise ValueError(f"Item {item.name} was not configured in this Structure.")
        if shouldBeMany:
            ls = self.d[gid][item.name]
            if not isinstance(ls, list): raise ValueError("Tried to add a value to a non-Many item.")
            return ls

    def set(self, gid: api.Snowflake, item: One, value: api.Snowflake):
        self._check(gid, item)
        self.d[gid][item.name] = value

    def unset(self, gid: api.Snowflake, item: One):
        self._check(gid, item)
        self.d[gid][item.name] = None

    def add(self, gid: api.Snowflake, item: Many, value: api.Snowflake):
        orig = self._check(gid, item, True)
        if value in orig: return False
        orig.append(value)
        return True

    def rm(self, gid: api.Snowflake, item: Many, value: api.Snowflake):
        orig = self._check(gid, item, True)
        if not value in orig: return False
        orig.remove(value)
        return True

    def clear(self, gid: api.Snowflake, item: Many):
        orig = self._check(gid, item, True)
        self.d[gid][item.name] = []
