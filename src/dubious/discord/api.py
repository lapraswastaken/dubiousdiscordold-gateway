
from __future__ import annotations

import datetime as dt
from typing import Any, Tuple

from dubious.discord.enums import InteractionEventTypes, opcode, tcode
from pydantic import BaseModel, Field


class Snowflake(str):
    def __init__(self, r: str|int):
        self.id = int(r) if isinstance(r, str) else r
        self.timestamp = (self.id >> 22) + 1420070400000
        self.workerID = (self.id & 0x3E0000) >> 17
        self.processID = (self.id & 0x1F000) >> 12
        self.increment = self.id & 0xFFF

    def __repr__(self):
        return str(self.id)

    def __str__(self) -> str:
        return repr(self)

    def __hash__(self):
        return self.id

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, self.__class__):
            try:
                return int(o) == self.id # type: ignore
            except TypeError:
                return False
        return o.id == self.id

    def __ne__(self, o: object) -> bool:
        return not self == o

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, (str, int)):
            raise TypeError(f"Snowflake cannot be created from {type(v)}")
        return cls(v)

class DiscError(ValueError):
    def __init__(self, cls: type[Disc], data: dict, errors: str):
        self.cls = cls
        self.data = data
        self.errors = errors
        super().__init__(f"in {cls}, with the following data:\n{data}:\n{errors}")

class ErrorCodeMessage():
    code: str | None
    message: str | None

    def __init__(self, code: str | None, message: str | None):
        self.code = code
        self.message = message

class RequestError():
    errors: list[ErrorCodeMessage]

    def __init__(self, errors: list):
        self.errors = []
        for error in errors:
            self.errors.append(ErrorCodeMessage(**error))

class ObjectError():
    errors: dict[str, RequestError | ArrayError]

    def __init__(self, errors: dict[str, dict]):
        self.errors = {}
        for key, val in errors.items():
            if "_errors" in val:
                self.errors[key] = RequestError(val["_errors"])
            elif "0" in val:
                self.errors[key] = ArrayError(list(val.values()))
            else:
                raise ValueError("Wrong type for ObjectError")

class ArrayError():

    items: list[ObjectError] = []

    def __init__(self, errors: list[dict]):
        self.items = []
        for error in errors:
            self.items.append(ObjectError(error))

class Error(ErrorCodeMessage):
    errors: RequestError | ObjectError | ArrayError | None
    # only present in HTTP code 429 (Rate Limit)
    retry_after: float | None

    def __init__(self, code: str | None, message: str | None, errors: dict | None=None, retry_after: float | None=None, **kwargs):
        super().__init__(code, message)
        self.retry_after = retry_after

        if not errors:
            self.errors = None
        elif "0" in errors:
            self.errors = ArrayError(list(errors.values()))
        elif "_errors" in errors:
            self.errors = RequestError(errors["_errors"])
        else:
            self.errors = ObjectError(errors)

class Disc(BaseModel):
    def __init__(self, **data: Any) -> None:
        # try:
            super().__init__(**data)
        # except ValidationError as e:
            # raise DiscError(self.__class__, data, e.json())
        #print(f"{self.__class__.__name__}:\n{data}\nactual:\n{self.debug()}\n")

    class Config:
        allow_population_by_field_name = True

    def debug(self, tab=0, *, leadingNewline=True, ignoreNested=False):
        s = ""
        maxFieldLen = max(len(fieldName) for fieldName in self.__fields__)
        for key, value in self:
            tabulation = tab * "  "
            padding = (maxFieldLen - len(key)) * " "
            if isinstance(value, Disc):
                fixed = value.debug(tab+1) if not ignoreNested else f"{value.__class__.__name__}(...)"
            else:
                fixed = str(value)
            s += ("\n" if leadingNewline else "") + f"{tabulation}{key}{padding} = {fixed}"
        return s

_Cast_op: dict[opcode, Disc] = {}
_Cast_t: dict[tcode, Disc] = {}
def op(op: opcode):
    def register(cls):
        _Cast_op[op] = cls
        return cls
    return register
def t(t: tcode):
    def register(cls):
        _Cast_t[t] = cls
        return cls
    return register

t_APIData = dict | bool | Disc | None

def castInner(p: Payload):
    data: t_APIData
    if p.op in _Cast_op:
        data = _Cast_op[p.op].parse_obj(p.d)
    elif p.t in _Cast_t and isinstance(p.t, tcode):
        data = _Cast_t[p.t].parse_obj(p.d)
    else:
        data = p.d if hasattr(p, "d") else {}
    return data

class IDable(Disc):
    id: Snowflake

class Payload(Disc):
    op: opcode
    t: tcode | str | None
    s: int | None
    d: t_APIData

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        # We want to assign explicitly the data to d if it's a Disc,
        #  otherwise it defaults to casting the object to a dict.
        if isinstance(data["d"], Disc):
            self.d = data["d"]

# https://discord.com/developers/docs/topics/gateway#activity-object-activity-structure
class Activity(Disc):
    # guaranteed
    name:       str
    type:       int
    created_at: int

    # not guaranteed
    url:            str                 | None
    timestamps:     ActivityTimestamps  | None
    application_id: Snowflake           | None
    details:        str                 | None
    state:          str                 | None
    emoji:          ActivityEmoji       | None
    party:          ActivityParty       | None
    assets:         ActivityAssets      | None
    secrets:        ActivitySecrets     | None
    instance:       bool                | None
    flags:          int                 | None
    buttons:   list[ActivityButton]     | None

# https://discord.com/developers/docs/topics/gateway#activity-object-activity-buttons
class ActivityButton(Disc):
    # guaranteed
    label: str
    url:   str

# https://discord.com/developers/docs/topics/gateway#activity-object-activity-assets
class ActivityAssets(Disc):
    # not guaranteed
    large_image: str | None
    large_text:  str | None
    small_image: str | None
    small_text:  str | None

# https://discord.com/developers/docs/topics/gateway#activity-object-activity-emoji
class ActivityEmoji(Disc):
    # guaranteed
    name: str

    # not guaranteed
    id:       Snowflake | None
    animated: bool      | None

# https://discord.com/developers/docs/topics/gateway#activity-object-activity-party
class ActivityParty(Disc):
    # not guaranteed
    id:   str             | None
    size: Tuple[int, int] | None

# https://discord.com/developers/docs/topics/gateway#activity-object-activity-secrets
class ActivitySecrets(Disc):
    # not guaranteed
    join:     str | None
    spectate: str | None
    match:    str | None

# https://discord.com/developers/docs/topics/gateway#activity-object-activity-timestamps
class ActivityTimestamps(Disc):
    # not guaranteed
    start: int | None
    end:   int | None

# https://discord.com/developers/docs/resources/channel#allowed-mentions-object-allowed-mentions-structure
class AllowedMentions(Disc):
    parse: list[str] # contains any or none of roles, users, everyone

    roles:   list[Snowflake]
    users:   list[Snowflake]
    replied_user: bool

# https://discord.com/developers/docs/resources/application#application-object-application-structure
class Application(IDable):
    id:                     Snowflake
    name:                   str
    icon:                   str
    description:            str
    bot_public:             bool
    bot_require_code_grant: bool
    summary:                str
    verify_key:             str
    team:                   dict

    rpc_origins:     list[str]      | None
    terms_of_service_url: str       | None
    privacy_policy_url:   str       | None
    owner:                User      | None
    guild_id:             Snowflake | None
    primary_sku_id:       Snowflake | None
    slug:                 str       | None
    cover_image:          str       | None
    flags:                int       | None

# https://discord.com/developers/docs/interactions/application-commands#application-command-object-application-command-structure
class ApplicationCommand(IDable):
    # guaranteed
    id:             Snowflake
    application_id: Snowflake
    name:           str
    description:    str
    version:        Snowflake

    # not guaranteed
    guild_id:                   Snowflake                  | None
    options:               list[ApplicationCommandOption]  | None
    default_permission:         bool                       | None
    default_member_permissions: int                        | None
    type:                       int = 1

# https://discord.com/developers/docs/interactions/application-commands#application-command-object-application-command-option-structure
class ApplicationCommandOption(Disc):
    # guaranteed
    type:        int
    name:        str
    description: str

    # not guaranteed
    required:     bool                             | None
    choices: list[ApplicationCommandOptionChoice]  | None
    options: list[ApplicationCommandOption]        | None

# https://discord.com/developers/docs/interactions/application-commands#application-command-object-application-command-option-choice-structure
class ApplicationCommandOptionChoice(Disc):
    # guaranteed
    name: str
    value: Any

# https://discord.com/developers/docs/resources/channel#attachment-object-attachment-structure
class Attachment(Disc):
    # guaranteed
    filename:  str
    size:      int
    url:       str
    proxy_url: str

    # not guaranteed
    content_type: str  | None
    height:       int  | None
    width:        int  | None
    ephemeral:    bool | None

# https://discord.com/developers/docs/resources/audit-log#audit-log-object-audit-log-structure
class AuditLog(Disc):
    audit_log_entries: list[AuditLogEntry]
    integrations:      list[Integration]
    threads:           list[Channel]
    users:             list[User]
    webhooks:          list[Webhook]

# https://discord.com/developers/docs/resources/audit-log#audit-log-entry-object
class AuditLogEntry(IDable):
    id:          Snowflake
    target_id:   str       | None = ... # type: ignore
    user_id:     Snowflake | None = ... # type: ignore 
    action_type: int
    
    changes: list[AuditLogEntryChange] | None
    options:      AuditLogEntryOptions | None
    reason:       str                  | None

# https://discord.com/developers/docs/resources/audit-log#audit-log-change-object-audit-log-change-structure
class AuditLogEntryChange(Disc):
    key: str

    new_value: Any | None
    old_value: Any | None

# https://discord.com/developers/docs/resources/audit-log#audit-log-entry-object-optional-audit-entry-info
class AuditLogEntryOptions(Disc):
    channel_id:         Snowflake | None
    count:              str       | None
    delete_member_days: str       | None
    id:                 Snowflake | None
    members_removed:    str       | None
    message_id:         Snowflake | None
    role_name:          str       | None

# https://discord.com/developers/docs/resources/channel#channel-object-channel-structure
@t(tcode.ChannelCreate)
@t(tcode.ChannelUpdate)
@t(tcode.ChannelDelete)
@t(tcode.ThreadCreate)
@t(tcode.ThreadUpdate)
@t(tcode.ThreadDelete)
class Channel(IDable):
    # guaranteed
    id: Snowflake
    type: int
    
    # not guaranteed
    guild_id:                      Snowflake       | None
    position:                      int             | None
    permission_overwrites:    list[Overwrite]      | None
    name:                          str             | None
    topic:                         str             | None
    nsfw:                          bool            | None
    last_message_id:               Snowflake       | None
    bitrate:                       int             | None
    user_limit:                    int             | None
    rate_limit_per_user:           int             | None
    recipients:               list[User]           | None
    icon:                          str             | None
    owner_id:                      Snowflake       | None
    application_id:                Snowflake       | None
    parent_id:                     Snowflake       | None
    last_pin_timestamp:            dt.datetime     | None
    rtc_region:                    str             | None
    video_quality_mode:            int             | None
    message_count:                 int             | None
    member_count:                  int             | None
    thread_metadata:               ThreadMetadata  | None
    member:                        ThreadMember    | None
    default_auto_archive_duration: int             | None
    permissions:                   str             | None

# https://discord.com/developers/docs/resources/channel#channel-mention-object-channel-mention-structure
class ChannelMention(IDable):
    # guaranteed
    id:       Snowflake
    guild_id: Snowflake
    type:     int
    name:     str

# https://discord.com/developers/docs/topics/gateway#channel-pins-update
@t(tcode.ChannelPinsUpdate)
class ChannelPinsUpdate(Disc):
    # guaranteed
    channel_id: Snowflake

    # not guaranteed
    guild_id:           Snowflake   | None
    last_pin_timestamp: dt.datetime | None

# https://discord.com/developers/docs/topics/gateway#client-status-object
class ClientStatus(Disc):
    # not guaranteed
    desktop: str | None
    mobile:  str | None
    web:     str | None

# https://discord.com/developers/docs/resources/channel#embed-object-embed-structure
class Embed(Disc):
    # not guaranteed
    title:       str            | None
    type:        str            | None
    description: str            | None
    url:         str            | None
    timestamp:   dt.datetime    | None
    color:       int            | None
    footer:      EmbedFooter    | None
    image:       EmbedMedia     | None
    thumbnail:   EmbedMedia     | None
    video:       EmbedMedia     | None
    provider:    EmbedProvider  | None
    author:      EmbedAuthor    | None
    fields: list[EmbedField]    | None

# https://discord.com/developers/docs/resources/channel#embed-object-embed-author-structure
class EmbedAuthor(Disc):
    # not guaranteed
    name:           str | None
    url:            str | None
    icon_url:       str | None
    proxy_icon_url: str | None

# https://discord.com/developers/docs/resources/channel#embed-object-embed-field-structure
class EmbedField(Disc):
    # guaranteed
    name:  str
    value: str

    # not guaranteed
    inline: bool | None

# https://discord.com/developers/docs/resources/channel#embed-object-embed-footer-structure
class EmbedFooter(Disc):
    # guaranteed
    text: str

    # not guaranteed
    icon_url:       str | None
    proxy_icon_url: str | None

# https://discord.com/developers/docs/resources/channel#embed-object-embed-image-structure
# https://discord.com/developers/docs/resources/channel#embed-object-embed-thumbnail-structure
# https://discord.com/developers/docs/resources/channel#embed-object-embed-video-structure
class EmbedMedia(Disc):
    # not guaranteed
    url:       str | None
    proxy_url: str | None
    height:    int | None
    width:     int | None

# https://discord.com/developers/docs/resources/channel#embed-object-embed-provider-structure
class EmbedProvider(Disc):
    # not guaranteed
    name: str | None
    url:  str | None

# https://discord.com/developers/docs/resources/emoji#emoji-object-emoji-structure
class Emoji(Disc):
    id: str   | None
    name: str | None

    roles:     list[Snowflake] | None
    user:           User       | None
    require_colons: bool       | None
    managed:        bool       | None
    animated:       bool       | None
    available:      bool       | None

# https://discord.com/developers/docs/resources/guild#guild-object-guild-structure
@t(tcode.GuildCreate)
@t(tcode.GuildUpdate)
class Guild(IDable):
    # guaranteed
    id:                            Snowflake
    name:                          str
    icon:                          str       | None = ... #type: ignore
    splash:                        str       | None = ... #type: ignore
    discovery_splash:              str       | None = ... #type: ignore
    owner_id:                      Snowflake
    afk_channel_id:                Snowflake | None = ... #type: ignore
    afk_timeout:                   int
    verification_level:            int
    default_message_notifications: int
    explicit_content_filter:       int
    roles:                    list[Role]
    emojis:                   list[Emoji]
    features:                 list[str]
    mfa_level:                     int
    application_id:                Snowflake | None = ... #type: ignore
    system_channel_id:             Snowflake | None = ... #type: ignore
    system_channel_flags:          int
    rules_channel_id:              Snowflake | None = ... #type: ignore
    vanity_url_code:               str       | None = ... #type: ignore
    description:                   str       | None = ... #type: ignore
    banner:                        str       | None = ... #type: ignore
    premium_tier:                  int
    preferred_locale:              str
    public_updates_channel_id:     Snowflake | None = ... #type: ignore
    nsfw_level:                    int

    # guaranteed in GUILD_CREATE
    widget_enabled:       bool           | None
    widget_channel_id:    Snowflake      | None
    joined_at:            str            | None
    large:                bool           | None
    unavailable:          bool           | None
    member_count:         int            | None
    voice_states:    list[VoiceState]    | None
    members:         list[Member]        | None
    channels:        list[Channel]       | None
    presences:       list[Presence]      | None
    stage_instances: list[StageInstance] | None
    
    application_command_counts:   dict[int, int] | None
    premium_progress_bar_enabled: bool           | None
    application_command_count:    int            | None
    lazy:                         bool           | None
    threads:                 list[Channel]       | None
    nsfw:                         bool           | None

    # not guaranteed
    icon_hash:                  str            | None
    region:                     str            | None
    max_presences:              int            | None
    max_members:                int            | None
    premium_subscription_count: int            | None
    max_video_channel_users:    int            | None
    approximate_member_count:   int            | None
    approximate_presence_count: int            | None
    welcome_screen:             WelcomeScreen  | None

# https://discord.com/developers/docs/topics/gateway#guild-emojis-update
@t(tcode.GuildEmojisUpdate)
class GuildEmojisUpdate(Disc):
    guild_id:    Snowflake
    emojis: list[Emoji]

# https://discord.com/developers/docs/topics/gateway#guild-integrations-update
@t(tcode.GuildIntegrationsUpdate)
class GuildIntegrationsUpdate(Disc):
    guild_id: Snowflake

# https://discord.com/developers/docs/topics/gateway#guild-member-update
@t(tcode.GuildMemberUpdate)
class GuildMemberUpdate(Disc):
    guild_id:   Snowflake
    roles: list[Snowflake]
    user:       User
    avatar:     str         | None
    joined_at:  dt.datetime

    nick:                         str         | None
    premium_since:                dt.datetime | None
    deaf:                         bool        | None
    mute:                         bool        | None
    pending:                      bool        | None
    communication_disabled_until: dt.datetime | None

# https://discord.com/developers/docs/topics/gateway#guild-members-chunk
@t(tcode.GuildMembersChunk)
class GuildMembersChunk(Disc):
    guild_id:      Snowflake
    members: list[Member]
    chunk_index:   int
    chunk_count:   int

    not_found: list           | None
    presences: list[Presence] | None
    nonce:          str       | None

# https://discord.com/developers/docs/topics/gateway#guild-ban-add
@t(tcode.GuildBanAdd)
# https://discord.com/developers/docs/topics/gateway#guild-ban-remove
@t(tcode.GuildBanRemove)
# https://discord.com/developers/docs/topics/gateway#guild-member-remove
@t(tcode.GuildMemberRemove)
class GuildMembershipChange(Disc):
    guild_id: Snowflake
    user:     User

# https://discord.com/developers/docs/topics/gateway#guild-role-create
@t(tcode.GuildRoleCreate)
# https://discord.com/developers/docs/topics/gateway#guild-role-update
@t(tcode.GuildRoleUpdate)
# https://discord.com/developers/docs/topics/gateway#guild-role-delete
@t(tcode.GuildRoleDelete)
class GuildRoleChange(Disc):
    guild_id: Snowflake
    role:     Role

# https://discord.com/developers/docs/topics/gateway#guild-stickers-update
@t(tcode.GuildStickersUpdate)
class GuildStickersUpdate(Disc):
    guild_id:      Snowflake
    stickers: list[Sticker]

# https://discord.com/developers/docs/topics/gateway#hello-hello-structure
@op(opcode.Hello)
class Hello(Disc):
    heartbeat_interval: int

# https://discord.com/developers/docs/resources/guild#integration-object-integration-structure
class Integration(IDable):
    id:      Snowflake
    name:    str
    type:    str
    enabled: bool

    syncing:             bool                    | None
    role_id:             Snowflake               | None
    enable_emoticons:    bool                    | None
    expire_behavior:     int                     | None
    expire_grace_period: int                     | None
    user:                User                    | None
    account:             IntegrationAccount      | None
    synced_at:           str                     | None
    subscriber_count:    int                     | None
    revoked:             bool                    | None
    application:         IntegrationApplication  | None

# https://discord.com/developers/docs/resources/guild#integration-account-object-integration-account-structure
class IntegrationAccount(IDable):
    id:   Snowflake
    name: str

# https://discord.com/developers/docs/resources/guild#integration-application-object-integration-application-structure
class IntegrationApplication(IDable):
    id:          Snowflake
    name:        str
    icon:        str | None = ... #type: ignore
    description: str
    summary:     str

    bot: User | None

# https://discord.com/developers/docs/interactions/receiving-and-responding#interaction-object-interaction-structure
# https://discord.com/developers/docs/topics/gateway#interaction-create
@t(tcode.InteractionCreate)
class Interaction(IDable):
    # guaranteed
    id:             Snowflake
    application_id: Snowflake
    type:           InteractionEventTypes
    token:          str
    version:        int

    # not guaranteed
    data:       InteractionData  | None
    guild_id:   Snowflake        | None
    channel_id: Snowflake        | None
    member:     Member           | None
    user:       User             | None
    message:    Message          | None

# https://discord.com/developers/docs/interactions/receiving-and-responding#interaction-object-interaction-data-structure
class InteractionData(Disc):
    # guaranteed for application command
    id:   Snowflake | None
    name: str       | None
    type: int       | None
    
    # not guaranteed for application command
    resolved:     InteractionCommandDataResolved | None
    options: list[InteractionCommandDataOption]  | None

    # not guaranteed for component
    custom_id:       str            | None
    component_type:  int            | None
    values:     list[SelectOption]  | None
    target_id:       Snowflake      | None

# https://discord.com/developers/docs/interactions/application-commands#application-command-object-application-command-interaction-data-option-structure
class InteractionCommandDataOption(Disc):
    # guaranteed
    name: str
    type: int

    # not guaranteed
    value:        Any                           | None
    options: list[InteractionCommandDataOption] | None

# https://discord.com/developers/docs/interactions/receiving-and-responding#interaction-object-resolved-data-structure
class InteractionCommandDataResolved(Disc):
    # not guaranteed
    users:    dict[Snowflake, User]    | None
    members:  dict[Snowflake, Member]  | None
    roles:    dict[Snowflake, Role]    | None
    channels: dict[Snowflake, Channel] | None

# https://discord.com/developers/docs/interactions/receiving-and-responding#interaction-response-object-interaction-response-structure
class InteractionResponse(Disc):
    # guaranteed
    type: int
    # not guaranteed
    data: InteractionResponseData | None

# https://discord.com/developers/docs/interactions/receiving-and-responding#interaction-response-object-interaction-callback-data-structure
class InteractionResponseData(Disc):
    tts:              bool
    content:          str
    embeds:      list[Embed]
    allowed_mentions: AllowedMentions
    flags:            int
    components:  list[MessageComponent]

# https://discord.com/developers/docs/topics/gateway#invite-create
@t(tcode.InviteCreate)
class InviteCreate(Disc):
    # guaranteed
    channel_id: Snowflake
    code:       str
    created_at: dt.datetime
    max_age:    int
    max_uses:   int
    temporary:  bool
    uses:       int
    # not guaranteed
    guild_id:           Snowflake           | None
    inviter:            User                | None
    target_type:        int                 | None
    target_user:        User                | None
    target_application: PartialApplication  | None


# https://discord.com/developers/docs/resources/guild#guild-member-object-guild-member-structure
@t(tcode.GuildMemberAdd)
class Member(Disc):
    # guaranteed
    roles: list[Snowflake]
    joined_at:  str
    # not guaranteed
    deaf:          bool  | None
    mute:          bool  | None
    user:          User  | None
    nick:          str   | None
    premium_since: str   | None
    pending:       bool  | None
    is_pending:    bool  | None
    permissions:   str   | None
    avatar:        str   | None
    # https://discord.com/developers/docs/topics/gateway#guild-member-add-guild-member-add-extra-fields
    # only with tcode.GuildMemberAdd
    guild_id:      Snowflake | None

# https://discord.com/developers/docs/resources/channel#message-object-message-structure
# https://discord.com/developers/docs/topics/gateway#message-create
@t(tcode.MessageCreate)
# https://discord.com/developers/docs/topics/gateway#message-update
@t(tcode.MessageUpdate)
class Message(IDable):
    id: Snowflake
    # guaranteed
    channel_id:         Snowflake
    author:             User
    content:            str
    timestamp:          dt.datetime
    edited_timestamp:   dt.datetime | None = Field(...)
    tts:                bool
    mention_everyone:   bool
    mentions:      list[User]
    mention_roles: list[Snowflake]
    attachments:   list[Attachment]
    embeds:        list[Embed]
    pinned:             bool
    type:               int
    # not guaranteed
    guild_id:              Snowflake          | None
    member:                Member             | None
    mention_channels: list[ChannelMention]    | None
    reactions:        list[Reaction]          | None
    webhook_id:            Snowflake          | None
    activity:              MessageActivity    | None
    application:           Application        | None
    application_id:        Snowflake          | None
    message_reference:     MessageReference   | None
    flags:                 int                | None
    stickers:         list[Sticker]           | None
    referenced_message:    Message            | None
    interaction:           MessageInteraction | None
    thread:                Channel            | None
    components:       list[MessageComponent]  | None

    def jump_url(self):
        return f"https://discordapp.com/channels/{self.guild_id}/{self.channel_id}/{self.id}"

# https://discord.com/developers/docs/resources/channel#message-object-message-activity-structure
class MessageActivity(Disc):
    # guaranteed
    type: int
    # not guaranteed
    party_id: str | None

# https://discord.com/developers/docs/interactions/message-components#component-object-component-structure
class MessageComponent(Disc):
    # guaranteed
    type: int
    # not guaranteed
    style:           int               | None
    label:           str               | None
    emoji:           Emoji             | None
    custom_id:       str               | None
    url:             str               | None
    options:    list[SelectOption]     | None
    disabled:        bool              | None
    placeholder:     str               | None
    min_values:      int               | None
    max_values:      int               | None
    components: list[MessageComponent] | None

# https://discord.com/developers/docs/topics/gateway#message-delete
@t(tcode.MessageDelete)
class MessageDelete(IDable):
    # guaranteed
    id:         Snowflake
    channel_id: Snowflake
    # not guaranteed
    guild_id: Snowflake | None

# https://discord.com/developers/docs/interactions/receiving-and-responding#message-interaction-object-message-interaction-structure
class MessageInteraction(Disc):
    id:   Snowflake
    type: int
    name: str
    user: User

# https://discord.com/developers/docs/topics/gateway#message-reaction-add
@t(tcode.MessageReactionAdd)
# https://discord.com/developers/docs/topics/gateway#message-reaction-remove
@t(tcode.MessageReactionRemove)
class MessageReactionChange(Disc):
    # guaranteed
    user_id:    Snowflake
    channel_id: Snowflake
    message_id: Snowflake
    emoji:      Emoji
    # not guaranteed
    guild_id: Snowflake | None
    member:   Member    | None

# https://discord.com/developers/docs/resources/channel#message-reference-object-message-reference-structure
class MessageReference(Disc):
    # not guaranteed
    message_id:         Snowflake | None
    channel_id:         Snowflake | None
    guild_id:           Snowflake | None
    fail_if_not_exists: bool      | None

# https://discord.com/developers/docs/resources/channel#overwrite-object
class Overwrite(IDable):
    id:    Snowflake
    type:  int
    allow: str
    deny:  str

# https://discord.com/developers/docs/topics/gateway#ready
class PartialApplication(IDable):
    id:    Snowflake
    flags: int



# https://discord.com/developers/docs/topics/gateway#presence-update
@t(tcode.PresenceUpdate)
class Presence(Disc):
    # guaranteed
    user:            User
    guild_id:        Snowflake
    status:          str
    activities: list[Activity]
    client_status:   ClientStatus

# https://discord.com/developers/docs/resources/channel#reaction-object-reaction-structure
class Reaction(Disc):
    # guaranteed
    count: int
    me:    bool
    emoji: Emoji

# https://discord.com/developers/docs/topics/gateway#ready
@t(tcode.Ready)
class Ready(Disc):
    v:             int
    user:          User
    guilds:   list[UnavailableGuild]
    session_id:    str
    application:   PartialApplication

# https://discord.com/developers/docs/topics/permissions#role-object-role-structure
class Role(IDable):
    id:          Snowflake
    name:        str
    color:       int
    hoist:       bool
    position:    int
    permissions: str
    managed:     bool
    mentionable: bool

    tags:          RoleTags  | None
    unicode_emoji: str       | None
    icon:          Emoji     | None

    def mention(self):
        return f"<@&{self.id}>"

# https://discord.com/developers/docs/topics/permissions#role-object-role-tags-structure
class RoleTags(Disc):
    bot_id:             Snowflake | None
    integration_id:     Snowflake | None
    premium_subscriber: bool      | None

# https://discord.com/developers/docs/interactions/message-components#select-menu-object-select-option-structure
class SelectOption(Disc):
    # guaranteed
    label: str
    value: str

    # not guaranteed
    description: str   | None
    emoji:       Emoji | None
    default:     bool  | None

# https://discord.com/developers/docs/resources/stage-instance#stage-instance-object-stage-instance-structure
class StageInstance(IDable):
    # guaranteed
    id:                    Snowflake
    guild_id:              Snowflake
    channel_id:            Snowflake
    topic:                 str
    privacy_level:         int
    discoverable_disabled: bool

# https://discord.com/developers/docs/resources/sticker#sticker-object-sticker-structure
class Sticker(IDable):
    # guaranteed
    id:          Snowflake
    name:        str
    description: str
    tags:        str
    format_type: int

    # not guaranteed
    pack_id:    Snowflake | None
    available:  bool      | None
    guild_id:   Snowflake | None
    user:       User      | None
    sort_value: int       | None

# https://discord.com/developers/docs/resources/channel#thread-member-object-thread-member-structure
@t(tcode.ThreadMemberUpdate)
class ThreadMember(Disc):
    # guaranteed
    join_timestamp: dt.datetime
    flags:          int

    # not guaranteed
    id:      Snowflake | None
    user_id: Snowflake | None

# https://discord.com/developers/docs/topics/gateway#thread-members-update
@t(tcode.ThreadMembersUpdate)
class ThreadMembersUpdate(IDable):
    # guaranteed
    id:           Snowflake
    guild_id:     Snowflake
    member_count: int

    # not guaranteed
    added_members:      list[ThreadMember] | None
    removed_member_ids: list[Snowflake]    | None

# https://discord.com/developers/docs/resources/channel#thread-metadata-object-thread-metadata-structure
class ThreadMetadata(Disc):
    # guaranteed
    archived:              bool
    auto_archive_duration: int
    archive_timestamp:     dt.datetime

    # not guaranteed
    locked: bool | None

# https://discord.com/developers/docs/resources/guild#unavailable-guild-object
@t(tcode.GuildDelete)
class UnavailableGuild(IDable):
    id: Snowflake

    unavailable: bool | None

# https://discord.com/developers/docs/resources/user#user-object-user-structure
class User(IDable):
    id:            Snowflake
    username:      str
    discriminator: str

    avatar:       str  | None
    bot:          bool | None
    system:       bool | None
    mfa_enabled:  bool | None
    locale:       str  | None
    verified:     bool | None
    email:        str  | None
    flags:        int  | None
    premium_type: int  | None
    public_flags: int  | None

# https://discord.com/developers/docs/resources/voice#voice-state-object-voice-state-structure
class VoiceState(Disc):
    channel_id:                 Snowflake | None = ... #type: ignore
    user_id:                    Snowflake
    session_id:                 str
    deaf:                       bool
    mute:                       bool
    self_deaf:                  bool
    self_mute:                  bool
    suppress:                   bool
    request_to_speak_timestamp: dt.datetime

    guild_id:    Snowflake | None
    member:      Member    | None
    self_stream: bool      | None
    self_video:  bool      | None

# https://discord.com/developers/docs/resources/webhook#webhook-object-webhook-structure
class Webhook(IDable):
    id:             Snowflake
    type:           int
    channel_id:     Snowflake | None = ... #type: ignore
    name:           str       | None = ... #type: ignore
    avatar:         str       | None = ... #type: ignore
    application_id: Snowflake | None = ... #type: ignore

    guild_id:       Snowflake | None
    user:           User      | None
    token:          str       | None
    source_guild:   Guild     | None
    source_channel: Channel   | None
    url:            str       | None

# https://discord.com/developers/docs/topics/gateway#webhooks-update
@t(tcode.WebhooksUpdate)
class WebhooksUpdate(Disc):
    guild_id:   Snowflake
    channel_id: Snowflake

# https://discord.com/developers/docs/resources/guild#welcome-screen-object-welcome-screen-structure
class WelcomeScreen(Disc):
    description:           str                   | None = ... #type: ignore
    welcome_channels: list[WelcomeScreenChannel]

# https://discord.com/developers/docs/resources/guild#welcome-screen-object-welcome-screen-channel-structure
class WelcomeScreenChannel(Disc):
    channel_id:  Snowflake
    description: str
    emoji_id:    Snowflake | None = ... #type: ignore
    emoji_name:  Snowflake | None = ... #type: ignore

def fuckyoupydantic(cls: type[BaseModel]):
    for subcls in cls.__subclasses__():
        fuckyoupydantic(subcls)
    cls.update_forward_refs()
fuckyoupydantic(Disc)
