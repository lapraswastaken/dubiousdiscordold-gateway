
import re
from dubious import Command, Chip, Ixn, Option, Pory2, api, enums

p_Tag = re.compile(r"<.(\d+)>")

class mu2OS(Pory2):
    # class Channels(Schema):
    #     rp = Schema.channel.multiple

    # class Roles(Schema):
    #     owner = Schema.role.single

    # supercommand = Record("mu2os",
    #     "Test functionality for mu2OS!",
    #     guildID=798023066718175252
    # )

    def __init__(self):
        super().__init__()
        self.count = 0

    @Command.make("say", "Say something!", guildID=798023066718175252)
    async def test(self, ixn: Ixn):
        pass

    @test.subcommand
    @Command.make("hello", "Say 'Hello'!")
    async def hello(self, ixn: Ixn):
        await ixn.respond("Hello")

    @Command.make("ping", "Responds with 'Pong!'", guildID=798023066718175252)
    async def ping(self, ixn: Ixn):
        await ixn.respond("Pong!")

    @Command.make("inc", "Increments and then prints a number.", guildID=798023066718175252)
    async def inc(self, ixn: Ixn):
        self.count += 1
        await ixn.respond(f"Number is now at {self.count}.")

    @Command.make("cat", "Repeats a given message.", [
        Option.make("message", "The message to repeat.", enums.CommandOptionTypes.String)
    ], guildID=798023066718175252)
    async def cat(self, ixn: Ixn, message: str):
        await ixn.respond(message)

    @Command.make("greet", "Says \"Hello!\" to another user.", [
        Option.make("user", "The user to greet.", enums.CommandOptionTypes.User)
    ], guildID=798023066718175252)
    async def greet(self, ixn: Ixn, user: api.User):
        await ixn.respond(f"Hello, {user.username}!", silent=True)

    @Command.make("id", "Gives the ID of the mentioned Discord tag (user/member, channel, or role).", [
        Option.make("tag", "Any Discord tag.", enums.CommandOptionTypes.String)
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
