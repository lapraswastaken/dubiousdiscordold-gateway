
from enum import Enum
from typing import Literal

IxnOriginal: Literal["@original"] = "@original"
Empty = "** **"

class opcode(int, Enum):
    Dispatch            = 0
    Heartbeat           = 1
    Identify            = 2
    PresenceUpdate      = 3
    VoiceStateUpdate    = 4
    Resume              = 6
    Reconnect           = 7
    GuildRequestMembers = 8
    InvalidSession      = 9
    Hello               = 10
    HeartbeatAck        = 11

class tcode(str, Enum):
    Ready =                      "READY"
    Resumed =                    "RESUMED"
    Reconnect =                  "RECONNECT"
    InvalidSession =             "INVALID_SESSION"
    ApplicationCommandCreate =   "APPLICATION_COMMAND_CREATE"
    ApplicationCommandUpdate =   "APPLICATION_COMMAND_UPDATE"
    ApplicationCommandDelete =   "APPLICATION_COMMAND_DELETE"
    ChannelCreate =              "CHANNEL_CREATE"
    ChannelUpdate =              "CHANNEL_UPDATE"
    ChannelDelete =              "CHANNEL_DELETE"
    ChannelPinsUpdate =          "CHANNEL_PINS_UPDATE"
    ThreadCreate =               "THREAD_CREATE"
    ThreadUpdate =               "THREAD_UPDATE"
    ThreadDelete =               "THREAD_DELETE"
    ThreadListSync =             "THREAD_LIST_SYNC"
    ThreadMemberUpdate =         "THREAD_MEMBER_UPDATE"
    ThreadMembersUpdate =        "THREAD_MEMBERS_UPDATE"
    GuildCreate =                "GUILD_CREATE"
    GuildUpdate =                "GUILD_UPDATE"
    GuildDelete =                "GUILD_DELETE"
    GuildBanAdd =                "GUILD_BAN_ADD"
    GuildBanRemove =             "GUILD_BAN_REMOVE"
    GuildEmojisUpdate =          "GUILD_EMOJIS_UPDATE"
    GuildIntegrationsUpdate =    "GUILD_INTEGRATIONS_UPDATE"
    GuildMemberAdd =             "GUILD_MEMBER_ADD"
    GuildMemberRemove =          "GUILD_MEMBER_REMOVE"
    GuildMemberUpdate =          "GUILD_MEMBER_UPDATE"
    GuildMembersChunk =          "GUILD_MEMBERS_CHUNK"
    GuildRoleCreate =            "GUILD_ROLE_CREATE"
    GuildRoleUpdate =            "GUILD_ROLE_UPDATE"
    GuildRoleDelete =            "GUILD_ROLE_DELETE"
    GuildIntegrationCreate =     "GUILD_INTEGRATION_CREATE"
    GuildIntegrationUpdate =     "GUILD_INTEGRATION_UPDATE"
    GuildIntegrationDelete =     "GUILD_INTEGRATION_DELETE"
    GuildStickersUpdate =        "GUILD_STICKERS_UPDATE"
    InteractionCreate =          "INTERACTION_CREATE"
    InviteCreate =               "INVITE_CREATE"
    InviteDelete =               "INVITE_DELETE"
    MessageCreate =              "MESSAGE_CREATE"
    MessageUpdate =              "MESSAGE_EDIT"
    MessageDelete =              "MESSAGE_DELETE"
    MessageDeleteBulk =          "MESSAGE_DELETE_BULK"
    MessageReactionAdd =         "MESSAGE_REACTION_ADD"
    MessageReactionRemove =      "MESSAGE_REACTION_REMOVE"
    MessageReactionRemoveAll =   "MESSAGE_REACTION_REMOVE_ALL"
    MessageReactionRemoveEmoji = "MESSAGE_REACTION_REMOVE_EMOJI"
    PresenceUpdate =             "PRESENCE_UPDATE"
    StageInstanceCreate =        "STAGE_INSTANCE_CREATE"
    StageInstanceDelete =        "STAGE_INSTANCE_DELETE"
    StageInstanceUpdate =        "STAGE_INSTANCE_UPDATE"
    TypingStart =                "TYPING_START"
    UserUpdate =                 "USER_UPDATE"
    VoiceStateUpdate =           "VOICE_STATE_UPDATE"
    VoiceServerUpdate =          "VOICE_SERVER_UPDATE"
    WebhooksUpdate =             "WEBHOOKS_UPDATE"

    Disconnect = "DISCONNECT"

codes = opcode | tcode


class ApplicationCommandTypes(int, Enum):
    ChatInput  = 1
    PerUser    = 2
    PerMessage = 3

class ButtonStyles(int, Enum):
    Primary   = 1
    Secondary = 2
    Success   = 3
    Danger    = 4
    Link      = 5

class ChannelTypes(int, Enum):
    GuildText          = 0
    DM                 = 1
    GuildVoice         = 2
    GroupDM            = 3
    GuildCategory      = 4
    GuildNews          = 5
    GuildNewsThread    = 10
    GuildPublicThread  = 11
    GuildPrivateThread = 12
    GuildStageVoice    = 13
    GuildDirectory     = 14
    GuildForum         = 15

class HTTPResponseCode(int, Enum):
    """ https://discord.com/developers/docs/topics/opcodes-and-status-codes#http """
    OK                  = 200
    CREATED             = 201
    NO_CONTENT          = 204
    NOT_MODIFIED        = 304
    BAD_REQUEST         = 400
    UNAUTHORIZED        = 401
    FORBIDDEN           = 403
    NOT_FOUND           = 404
    METHOD_NOT_ALLOWED  = 405
    TOO_MANY_REQUESTS   = 429
    GATEWAY_UNAVAILABLE = 502

class CommandOptionTypes(int, Enum):
    SubCommand      = 1
    SubCommandGroup = 2
    String          = 3
    Integer         = 4
    Boolean         = 5
    User            = 6
    Member          = 6
    Channel         = 7
    Role            = 8
    Mentionable     = 9
    Number          = 10

class Intents(int, Enum):
    Guilds                 = 1 << 0
    GuildMembers           = 1 << 1
    GuildBans              = 1 << 2
    GuildEmojisAndStickers = 1 << 3
    GuildIntegrations      = 1 << 4
    GuildWebhooks          = 1 << 5
    GuildInvites           = 1 << 6
    GuildVoiceStates       = 1 << 7
    GuildPresences         = 1 << 8
    GuildMessages          = 1 << 9
    GuildMessageReactions  = 1 << 10
    GuildMessageTyping     = 1 << 11
    DirectMessages         = 1 << 12
    DirectMessageReactions = 1 << 13
    DirectMessageTyping    = 1 << 14

class InteractionEventTypes(int, Enum):
    Ping               = 1
    ApplicationCommand = 2
    MessageComponent   = 3
    Autocomplete       = 4
    ModalSubmit        = 5

class InteractionResponseTypes(int, Enum):
    """ https://discord.com/developers/docs/interactions/receiving-and-responding#interaction-response-object-interaction-callback-type """
    Pong           = 1
    CmdMessage     = 4
    CmdAckAndEdit  = 5
    CompAckAndEdit = 6
    CompEdit       = 7
    Autocomplete   = 8
    Modal          = 9

class IdentifyPermissions(int, Enum):
    CreateInstantInvite =     1 << 0
    KickMembers =             1 << 1
    BanMembers =              1 << 2
    Administrator =           1 << 3
    ManageChannels =          1 << 4
    ManageGuild =             1 << 5
    AddReactions =            1 << 6
    ViewAuditLog =            1 << 7
    PrioritySpeaker =         1 << 8
    Stream =                  1 << 9
    ViewChannel =             1 << 10
    SendMessages =            1 << 11
    SendTTSMessages =         1 << 12
    ManageMessages =          1 << 13
    EmbedLinks =              1 << 14
    AttachFiles =             1 << 15
    ReadMessageHistory =      1 << 16
    MentionEveryone =         1 << 17
    UseExternalEmojis =       1 << 18
    ViewGuildInsights =       1 << 19
    Connect =                 1 << 20
    Speak =                   1 << 21
    MuteMembers =             1 << 22
    DeafenMembers =           1 << 23
    MoveMembers =             1 << 24
    UseVAD =                  1 << 25
    ChangeNickname =          1 << 26
    ManageNicknames =         1 << 27
    ManageRoles =             1 << 28
    ManageWebhooks =          1 << 29
    ManageEmojisAndStickers = 1 << 30
    UseApplicationCommands =  1 << 31
    RequestToSpeak =          1 << 32
    ManageThreads =           1 << 34
    CreatePublicThreads =     1 << 35
    CreatePrivateThreads =    1 << 36
    UseExternalStickers =     1 << 37
    SendMessagesInThreads =   1 << 38
    StartEmbeddedActivities = 1 << 39

class JSONErrorCode(int, Enum):
    """ https://discord.com/developers/docs/topics/opcodes-and-status-codes#json """
    General            = 0
    UnknownMessage     = 10008
    Unauthorized       = 40001
    MissingAccess      = 50001
    InvalidFormBody    = 50035
