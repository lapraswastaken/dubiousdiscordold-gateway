
from dubious import Pory2, Handle, Learn, api

class MuOS(Pory2):
    @Handle(api.tcode.Ready)
    async def ready(self, _: api.Ready):
        print(f"{self._user.username} is ready!")
    
    @Learn("ping", "Responds with 'Pong!'")
    async def ping(self, ixn: api.Interaction):
        pass