
from pydantic import validator
from dubious.discord import api, enums

class Identify(api.Disc):
    token:      str
    intents:    int
    properties: dict

class Resume(api.Disc):
    token: str
    session: str
    seq: int | None

class CommandOptionChoice(api.Disc):
    name: str
    value: str

class CommandOption(api.Disc):
    name: str
    type: int
    description: str

    required: bool
    choices: list[CommandOptionChoice] | None

class Command(api.Disc):
    name: str
    type: int
    description: str
    options: list[CommandOption] | None
    guildID: api.Snowflake | None

class Noneable(api.Disc):
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

    title:       str               | None = None
    description: str               | None = None
    url:         str               | None = None
    timestamp:   str               | None = None
    color:       int               | None = None
    footer:      Footer          | None = None
    image:       Media           | None = None
    thumbnail:   Media           | None = None
    video:       Media           | None = None
    provider:    Provider        | None = None
    author:      Author          | None = None
    fields:      list[Field]     | None = None

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

class Message(api.Disc):
    content:          str        | None = None
    file:             bytes      | None = None
    reference:        str        | None = None
    embeds:      list[Embed]     | None = None
    components:  list[Component] | None = None
    tts: bool = False

class CallbackData(api.Disc):
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

class Response(api.Disc):
    type: enums.InteractionResponseTypes
    data: CallbackData