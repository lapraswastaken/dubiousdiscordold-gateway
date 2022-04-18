
from dubious import Pory2, Learn, api, enums, Ixn

class MuOS(Pory2):
    def __init__(self):
        super().__init__()
        self.count = 0

    @Learn("ping", "Responds with 'Pong!'", guildID=798023066718175252)
    async def ping(self, ixn: Ixn):
        await ixn.respond("Pong!")
    
    @Learn("inc", "Increments and then prints a number.", guildID=798023066718175252)
    async def inc(self, ixn: Ixn):
        self.count += 1
        await ixn.respond(f"Number is now at {self.count}.")

if __name__ == "__main__":
    with open("./sources/key.txt", "r") as f:
        token = f.read()

    MuOS().start(
        token,
        enums.Intents.Guilds |
        enums.Intents.GuildMessages |
        enums.Intents.GuildMessageReactions
    )