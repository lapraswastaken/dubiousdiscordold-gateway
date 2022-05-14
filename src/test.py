
from dubious.Machines import TR, Ixn, Option
from dubious.Pory import Chip, Pory, Pory2
from dubious.discord import enums

with open("./sources/key.txt", "r") as f:
    token = f.read()

class mu2OS(Pory2):
    @TR("hello", "Replies with 'Hello!'", guildID=798023066718175252)
    async def hello(self, ixn: Ixn):
        await ixn.respond("Hello!")
    
    @TR("cat", "Replies with the given input.", [
        Option("text", "The text to echo.", enums.CommandOptionTypes.String)
    ], guildID=798023066718175252)
    async def cat(self, ixn: Ixn, text: str):
        await ixn.respond(text)

def main():
    mychip = Chip()
    mu2OS().use(mychip)

    mychip.start(token, 0)

main()
