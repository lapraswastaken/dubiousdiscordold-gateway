
from typing import ClassVar

from pydantic import BaseModel

class Unjson(BaseModel):
    @classmethod
    def fromFile(cls, file: str):
        try:
            return cls.parse_file(file)
        except FileNotFoundError:
            return cls()

    def toFile(self, file: str):
        with open(file, "w") as f:
            f.write(self.json())

class JFile(Unjson):
    path: ClassVar[str]
    
    @classmethod
    def load(cls):
        return cls.fromFile(cls.path)
    
    def dump(self):
        return self.toFile(self.path)