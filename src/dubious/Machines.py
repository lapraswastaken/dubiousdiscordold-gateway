

import inspect
from typing import Any, Callable, Concatenate, Coroutine, TypeVar
from dubious.Interaction import Ixn

from dubious.Register import OrderedRegister, Register, t_Params
from dubious.discord import api, enums, make, rest

a_Data = api.Disc | bool | dict | None
t_BoundData = TypeVar("t_BoundData", bound=a_Data)
a_HandleCallback = Callable[[t_BoundData], Coroutine[Any, Any, None]]
a_HandleReference = enums.opcode | enums.tcode

class HM(OrderedRegister[a_HandleReference]):
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

class Dumps:
    def dump(self):
        pass

t_TMCallback = Callable[
    Concatenate[Any, Ixn, t_Params],
        Coroutine[Any, Any, Any]
]
a_TMReference = str
class TR(Register[a_TMReference]):

    name: str
    description: str
    options: list["Option"]
    guildID: api.Snowflake | None

    def __init__(self,
        name: str,
        description: str,
        options: list["Option"] | None=None,
        guildID: api.Snowflake | int | None=None
    ):
        self.name = name
        self.description = description
        self.options = options if options else []
        self._options = {option.name: option for option in self.options}
        self.guildID = api.Snowflake(guildID) if guildID else None

    def reference(self):
        return self.name

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
        return self._options.get(name)

    def dump(self):
        return make.Command(
            name=self.name,
            type=enums.ApplicationCommandTypes.ChatInput,
            description=self.description,
            options=[option.dump() for option in self.options] if self.options else None,
            guildID=self.guildID
        )

class Option(Dumps):
    name: str
    description: str
    type: enums.CommandOptionTypes
    required: bool
    choices: list["Choice"]

    def __init__(self, name: str, description: str, typ: enums.CommandOptionTypes, required: bool=True, choices: list | None=None):
        self.name = name
        self.description = description
        self.type = typ
        self.required = required
        self.choices = choices if choices else []

    def dump(self):
        return make.CommandOption(
            name=self.name,
            description=self.description,
            type=self.type,
            required=self.required,
            choices=[
                choice.dump() for choice in self.choices
            ] if self.choices else None
        )

class Choice(Dumps):
    name: str
    value: Any

    def __init__(self, name: str, value: Any):
        self.name = name
        self.value = value

    def dump(self):
        return make.CommandOptionChoice(
            name=self.name,
            value=self.value
        )
