

import abc
import inspect
from typing import Any, Callable, Concatenate, Coroutine, TypeVar
from typing_extensions import Self

from pydantic import Field
from dubious.Interaction import Ixn

from dubious.Register import OrderedRegister, Register, t_Params
from dubious.discord import api, enums, make, rest

a_Data = api.Disc | bool | dict | None
t_BoundData = TypeVar("t_BoundData", bound=a_Data)
a_HandleCallback = Callable[[t_BoundData], Coroutine[Any, Any, None]]
a_HandleReference = enums.opcode | enums.tcode

class Hidden(OrderedRegister[a_HandleReference]):
    func: a_HandleCallback[a_Data]
    # The code that the handler will be attached to.
    code: a_HandleReference
    # The lower the prio value, the sooner the handler is called.
    # This only applies to the ordering of handlers within one class - handlers of any superclass will always be called first.

    def __init__(self, ident: a_HandleReference, order=0):
        super().__init__(order)
        self.code = ident

    def reference(self):
        return self.code

class Technical(abc.ABC):
    name: str
    description: str
    type: int
    options: list["Technical"] = Field(default_factory=list)

    def __init__(self, name: str, description: str, type: int, options: list["Technical"]):
        self.name = name
        self.description = description
        self.type = type
        self.options = options

    def getOptionsByName(self):
        return {option.name: option for option in self.options}

    def reference(self):
        return self.name

    @classmethod
    def getPartsFromDObj(cls, dobj: api.ApplicationCommand | api.ApplicationCommandOption):
        return dict(
            name=dobj.name,
            description=dobj.description,
            type=dobj.type,
            options=[Option.fromDiscord(
                opt
            ) for opt in (dobj.options if dobj.options else [])],
        )

    @classmethod
    def fromDiscord(cls, dobj: api.ApplicationCommand | api.ApplicationCommandOption):
        return cls(
            **cls.getPartsFromDObj(dobj)
        )

a_TechnicalReference = str
t_TMCallback = Callable[
    Concatenate[Any, Ixn, t_Params],
        Coroutine[Any, Any, Any]
]
class Record(Technical, Register[a_TechnicalReference]):
    """ A class that decorates chat input commands. """

    type = enums.ApplicationCommandTypes.ChatInput

    guildID: api.Snowflake | None = None

    def __init__(self, name: str, description: str, options: list["Technical"] | None=None, guildID: api.Snowflake | int | str | None=None):
        super().__init__(name, description, enums.ApplicationCommandTypes.ChatInput, options if options else [])
        self.guildID = api.Snowflake(guildID) if guildID else None

    def __call__(self, func: t_TMCallback[t_Params]):
        # Perform a quick check to see if all extra parameters in the function
        #  signature exist in the options list.
        sig = inspect.signature(func)
        for paramName in sig.parameters:
            param = sig.parameters[paramName]
            if (
                paramName == "self" or
                issubclass(param.annotation, Ixn) or
                param.annotation == inspect.Parameter.empty
            ): continue
            if not paramName in [option.name for option in self.options]:
                raise AttributeError(f"Parameter {paramName} was found in this command's function's signature, but it wasn't found in this command's options.")
        return super().__call__(func)

    def getOption(self, name: str):
        return self.getOptionsByName().get(name)

    @classmethod
    def getPartsFromObj(cls, dobj: api.ApplicationCommand):
        return dict(
            **super().getPartsFromDObj(dobj),
            guild_id=dobj.guild_id,
        )

class Option(Technical):
    required: bool
    choices: list["Choice"] = Field(default_factory=list)

    def __init__(self, name: str, description: str, type: enums.CommandOptionTypes, options: list["Technical"] | None=None, required: bool=True, choices: list["Choice"] | None=None):
        super().__init__(name, description, enums.ApplicationCommandTypes.ChatInput, options if options else [])
        self.required = required
        self.choices = choices if choices else []

    @classmethod
    def getPartsFromDObj(cls, dobj: api.ApplicationCommandOption):
        return dict(
            **super().getPartsFromDObj(dobj),
            required=dobj.required if dobj.required is not None else False,
            choices=[Choice(
                name=dchoice.name,
                value=dchoice.value
            ) for dchoice in (dobj.choices if dobj.choices else [])],
        )

class Choice(api.Disc):
    name:  str
    value: Any
