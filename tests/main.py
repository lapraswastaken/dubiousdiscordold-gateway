
from muOS import MuOS

with open("./sources/key.txt", "r") as f:
    token = f.read()

MuOS().start(token, 0)