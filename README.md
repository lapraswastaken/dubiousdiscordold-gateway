
# dubiousdiscord

A (yet to be fully-featured) Python package that wraps the official Discord API.

```python

import dubious as dd
from dubious import enums, api

class mu2OS(dd.Pory2):

    @dd.Command.make("ping", "Responds with 'Pong!'", guildID=798023066718175252)
    async def ping(self, ixn: dd.Ixn):
        await ixn.respond("Pong!")

    @dd.Command.make("cat", "Repeats a given message.", [
        dd.Option.make("message", "The message to repeat.", enums.CommandOptionTypes.String)
    ], guildID=798023066718175252)
    async def cat(self, ixn: dd.Ixn, message: str):
        await ixn.respond(message)

    @dd.Command.make("greet", "Says \"Hello!\" to another user.", [
        dd.Option.make("user", "The user to greet.", enums.CommandOptionTypes.User)
    ], guildID=798023066718175252)
    async def greet(self, ixn: dd.Ixn, user: api.User):
        await ixn.respond(f"Hello, <@{user.username}>!", silent=True)

if __name__ == "__main__":
    with open("./key.txt", "r") as f:
        token = f.read()

    chip = Chip()
    mu2OS().use(chip)

    chip.start(
        token,
        enums.Intents.Guilds
    )
```
