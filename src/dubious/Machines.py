

import abc
import inspect
from typing import Any, Callable, Concatenate, Coroutine, Generic, TypeVar
from typing_extensions import Self

from pydantic import Field, PrivateAttr
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

a_RecordReference = str

t_TMCallback = Callable[
    Concatenate[Any, Ixn, t_Params],
        Coroutine[Any, Any, Any]
]
class Machine(Register[a_RecordReference], make.CommandPart, abc.ABC):
    _func: t_TMCallback = PrivateAttr()

    def reference(self) -> a_RecordReference:
        return self.name

    def __call__(self, func: t_TMCallback[t_Params]) -> Self:
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

    async def call(self, owner: Any, ixn: Ixn, **kwargs):
        subcommands: list[Machine] = []
        toRemove: list[str] = []
        for kwargname, kwarg in kwargs.items():
            if isinstance(kwarg, Machine):
                subcommands.append(kwarg)
                toRemove.append(kwargname)
        for remove in toRemove:
            kwargs.pop(remove)
        await super().call(owner, ixn, **kwargs)
        for subcommand in subcommands:
            await subcommand.call(owner, ixn, **kwargs)

    @classmethod
    @abc.abstractmethod
    def make(cls,
        name: str,
        description: str,
        type: enums.ApplicationCommandTypes | enums.CommandOptionTypes,
        options: list[make.CommandPart] | None=None,
    **kwargs) -> Self:
        return cls(
            name=name,
            description=description,
            type=type,
            options=options if options else [],
            **kwargs
        )

class Command(Machine, make.Command):
    """ A class that decorates chat input commands. """

    @classmethod
    def make(cls,
        name: str,
        description: str,
        options: list[make.CommandPart] | None=None,
        guildID: api.Snowflake | int | str | None=None
    ):
        return super().make(
            name=name,
            description=description,
            type=enums.ApplicationCommandTypes.ChatInput,
            options=options if options else [],
            guildID=api.Snowflake(guildID) if guildID else None,
        )

    def getOptionsByName(self):
        return {option.name: option for option in self.options}

    def getOption(self, name: str):
        return self.getOptionsByName().get(name)

    def subcommand(self, command: "Command"):
        option = Option.make(command.name, command.description, enums.CommandOptionTypes.SubCommand, None)
        option.__call__(command._func)
        self.options.append(option)
        return option

class Option(Machine, make.CommandOption):

    @classmethod
    def make(cls, name: str, description: str, type: enums.CommandOptionTypes, required: bool | None=True, choices: list[make.CommandOptionChoice] | None=None):
        return super().make(
            name=name,
            description=description,
            type=type,
            required=required,
            choices=choices if choices else [],
            options=[]
        )

def Choice(name: str, value: Any):
    return make.CommandOptionChoice(
        name=name,
        value=value
    )
