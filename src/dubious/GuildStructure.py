
import json
from typing import ClassVar, Iterator, Mapping
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

    def load(self):
        with open(self.path, "r") as f:
            j = json.load(f)
            for guildID in self.d:
                if not guildID in j: continue
                for name in self.d[guildID]:
                    if not name in j[guildID]: continue
                    self.d[guildID][name] = j[guildID][name]

    def write(self):
        with open(self.path, "w") as f:
            json.dump(self.d, f)
