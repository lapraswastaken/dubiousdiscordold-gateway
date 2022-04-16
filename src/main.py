
from dubious import Pory2, Handle, Learn, api

class MuOS(Pory2):
    @Handle(api.tcode.Ready)
    async def ready(self, _):
        print(f"{self._user.username} is ready!")
    
    @Learn("ping", "Responds with 'Pong!'")
    async def ping(self, ixn: api.Interaction):
        print("Pong!")

with open("./sources/key.txt", "r") as f:
    token = f.read()

MuOS().start(token, 0)