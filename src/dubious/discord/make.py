
from __future__ import annotations

import re
from pydantic import validator
from dubious.discord import api, enums

class Make(api.Disc):
    pass

pat_Snowflake = re.compile(r".*(\d+).*")
class Snowflake(api.Snowflake):
    def __init__(self, r: str):
        match = re.match(pat_Snowflake, r)
        if not match: raise ValueError()
        fixed, = match.groups()
        super().__init__(fixed)

class Identify(Make):
    token:      str
    intents:    int
    properties: dict

class Resume(Make):
    token: str
    session: str
    seq: int | None

class CommandOptionChoice(Make):
    name: str
    value: str

    def eq(self, o: api.ApplicationCommandOptionChoice):
        return (
            self.name == o.name and
            self.value == o.value
        )

class CommandPart(Make):
    name: str
    description: str
    type: enums.ApplicationCommandTypes | enums.CommandOptionTypes
    options: list[CommandPart]

    def __hash__(self):
        return hash((self.name, self.description, self.type, (hash(option) for option in self.options)))

    def eq(self, o: api.ApplicationCommand | api.ApplicationCommandOption) -> bool:
        return (
            self.name == o.name and
            self.type == o.type and
            self.description == o.description and
            (
                all([option.eq(otheroption)
                    for option, otheroption in zip(self.options, o.options)]
                ) if self.options and o.options
                    else None == o.options
            )
        )

class CommandOption(CommandPart):
    required: bool | None
    choices: list[CommandOptionChoice]

    def eq(self, o: api.ApplicationCommandOption) -> bool:
        return (
            super().eq(o) and
            self.required == o.required and
            (
                all([choice.eq(otherchoice)
                    for choice, otherchoice in zip(self.choices, o.choices)]
                ) if self.choices and o.choices
                    else None == o.choices
            )
        )

class Command(CommandPart):
    guildID: api.Snowflake | None

    def eq(self, o: api.ApplicationCommand):
        return (
            super().eq(o) and
            self.guildID == o.guild_id
        )

class Noneable(Make):
    class Config:
        exclude_none = True

class Footer(Noneable):
    text:     str
    icon_url: str | None = None

class Media(Noneable):
    url:       str | None = None
    proxy_url: str | None = None
    width:     int | None = None
    height:    int | None = None

class Provider(Noneable):
    name: str | None = None
    url:  str | None = None

class Author(Noneable):
    name:           str | None = None
    url:            str | None = None
    icon_url:       str | None = None
    proxy_icon_url: str | None = None

class Field(Noneable):
    name:   str
    value:  str

    inline: bool = False

class Embed(Noneable):
    type:        str = "rich"

    title:       str         | None = None
    description: str         | None = None
    url:         str         | None = None
    timestamp:   str         | None = None
    color:       int         | None = None
    footer:      Footer      | None = None
    image:       Media       | None = None
    thumbnail:   Media       | None = None
    video:       Media       | None = None
    provider:    Provider    | None = None
    author:      Author      | None = None
    fields:      list[Field] | None = None

class Emoji(Noneable):
    name: str       | None
    id:   api.Snowflake | None

    def __init__(self, emoji: str | api.Snowflake):
        super().__init__()
        if isinstance(emoji, api.Snowflake): self.id = emoji
        else: self.name = emoji

class Component(Noneable):
    type: int

class Row(Component):
    type: int = 1

    components: list[Component]

class HasEmoji(Noneable):
    emoji: Emoji | None = None
    @validator("emoji")
    def _emoji(cls, v: Emoji | api.Snowflake | str | None):
        if v:
            if isinstance(v, Emoji):
                return v
            else:
                return Emoji(emoji=v)
        else:
            return None

class Button(Component, HasEmoji):
    type:      int = 2

    style:     enums.ButtonStyles
    label:     str | None = None
    custom_id: str | None = None
    url:       str | None = None
    disabled: bool = False

class DropdownOption(HasEmoji):
    label:       str
    value:       str | None = None
    description: str | None = None
    default: bool = False

    @validator("value")
    def _value(cls, value: str | None, values):
        return value if value else values["label"]

class Dropdown(Component):
    type:        int = 3

    custom_id:   str
    options:     list[DropdownOption]

    placeholder: str | None = None
    min_values:  int | None = None
    max_values:  int | None = None
    disabled: bool = False

class Message(Make):
    content:          str        | None = None
    file:             bytes      | None = None
    reference:        str        | None = None
    embeds:      list[Embed]     | None = None
    components:  list[Component] | None = None
    tts: bool = False

class CallbackData(Make):
    pass

class RMessage(CallbackData):
    content:              str             | None = None
    embeds:          list[Embed]          | None = None
    allowed_mentions: api.AllowedMentions | None = None
    components:      list[Component]      | None = None
    attachments: list[api.Attachment]     | None = None

    flags = 0
    tts = False

class Modal(CallbackData):
    custom_id: str
    title:     str
    components: list[Component]

class Response(Make):
    type: enums.InteractionResponseTypes
    data: CallbackData

api.fuckyoupydantic(Make)
