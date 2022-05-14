
import re
from dubious import TR, Chip, Ixn, Option, Pory2, api, enums

p_Tag = re.compile(r"<.(\d+)>")

class mu2OS(Pory2):
    # class Channels(Schema):
    #     rp = Schema.channel.multiple

    # class Roles(Schema):
    #     owner = Schema.role.single

    def __init__(self):
        super().__init__()
        self.count = 0

    @TR("ping", "Responds with 'Pong!'", guildID=798023066718175252)
    async def ping(self, ixn: Ixn):
        await ixn.respond("Pong!")

    @TR("inc", "Increments and then prints a number.", guildID=798023066718175252)
    async def inc(self, ixn: Ixn):
        self.count += 1
        await ixn.respond(f"Number is now at {self.count}.")

    @TR("cat", "Repeats a given message.", [
        Option("message", "The message to repeat.", enums.CommandOptionTypes.String)
    ], guildID=798023066718175252)
    async def cat(self, ixn: Ixn, message: str):
        await ixn.respond(message)

    @TR("greet", "Says \"Hello!\" to another user.", [
        Option("user", "The user to greet.", enums.CommandOptionTypes.User)
    ], guildID=798023066718175252)
    async def greet(self, ixn: Ixn, user: api.User):
        await ixn.respond(f"Hello, {user.username}!", silent=True)

    @TR("id", "Gives the ID of the mentioned Discord tag (user/member, channel, or role).", [
        Option("tag", "Any Discord tag.", enums.CommandOptionTypes.String)
    ], guildID=798023066718175252)
    async def id_(self, ixn: Ixn, tag: str):
        match = p_Tag.match(tag)
        if not match:
            await ixn.respond(f"Couldn't find an ID in the tag `{tag}`.")
            return
        await ixn.respond(f"That tag has the ID {match.group(1)}.")

if __name__ == "__main__":
    with open("./sources/key.txt", "r") as f:
        token = f.read()

    chip = Chip()
    mu2OS().use(chip)

    chip.start(
        token,
        enums.Intents.Guilds |
        enums.Intents.GuildMessages |
        enums.Intents.GuildMessageReactions
    )
