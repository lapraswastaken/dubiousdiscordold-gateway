
import abc
import inspect
from typing import Any, Callable, Concatenate, Coroutine, TypeVar
from typing_extensions import Self

from pydantic import PrivateAttr
from dubious.Interaction import Ixn

from dubious.Register import OrderedRegister, Register, t_Params
from dubious.discord import api, enums, make

a_Data = api.Disc | bool | dict | None
t_BoundData = TypeVar("t_BoundData", bound=a_Data)
a_HandleCallback = Callable[[t_BoundData], Coroutine[Any, Any, None]]
a_HandleReference = enums.opcode | enums.tcode

class Handle(OrderedRegister[a_HandleReference]):
    """ Decorates functions meant to be called when Discord sends a dispatch
        payload (a payload with opcode 0 and an existent tcode). """

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
    """ An abstract class meant to decorate functions that will be called when
        Discord sends a dispatch payload with an Interaction object. """

    _func: t_TMCallback = PrivateAttr()

    def reference(self) -> a_RecordReference:
        return self.name

    def __call__(self, func: t_TMCallback[t_Params]) -> Self:
        # Perform a quick check to see if all extra parameters in the function
        #  signature exist in the options list.
        sig = inspect.signature(func)
        for option in self.options:
            if not option.name in sig.parameters:
                raise AttributeError(f"Parameter `{option.name}` was found in this Command's Options list, but it wasn't found in this Command's function's signature.")
        return super().__call__(func)

    async def call(self, owner: Any, ixn: Ixn, *args: Any, **kwargs: Any):

        subcommand = None
        subcommandKwargs = {}
        for option in self.options:
            if isinstance(option, Machine) and option.name in kwargs:
                subcommand = option
                subcommandKwargs = kwargs.pop(option.name)
                break

        resultList = []
        results = await super().call(owner, ixn, *args, **kwargs)
        if isinstance(results, tuple): resultList += results
        elif results: resultList.append(results)

        if subcommand:
            return await subcommand.call(owner, ixn, *resultList, **subcommandKwargs)

    @classmethod
    @abc.abstractmethod
    def new(cls,
        name: str,
        description: str,
        type: enums.ApplicationCommandTypes | enums.CommandOptionTypes,
        options: list[make.CommandPart] | None=None,
    **kwargs) -> Self:
        """ Constructs this Machine without the need for kwargs. """

        return cls(
            name=name,
            description=description,
            type=type,
            options=options if options else [],
            **kwargs
        )

    def getOptionsByName(self):
        """ Returns a mapped dict of the name of each option in this Machine to
            its respective option. """

        return {option.name: option for option in self.options}

    def getOption(self, name: str):
        """ Returns the option in this Machine with the specified name. """

        for option in self.options:
            if isinstance(option, Machine):
                ret = option.getOption(name)
                if ret:
                    return ret
        return self.getOptionsByName().get(name)

    def subcommand(self, command: "Subcommand"):
        """ Returns an Option Machine to wrap a subsequent Command.
            That Command will be called after this one when its subcommand
            option is selected. """

        self.options.append(command)
        return command

class Command(Machine, make.Command):
    """ Decorates functions meant to be called when Discord sends a payload
        describing a ChatInput Interaction. """

    @classmethod
    def new(cls,
        name: str,
        description: str,
        options: list[make.CommandPart] | None=None,
        guildID: api.Snowflake | int | str | None=None
    ):
        return super().new(
            name=name,
            description=description,
            type=enums.ApplicationCommandTypes.ChatInput,
            options=options if options else [],
            guildID=api.Snowflake(guildID) if guildID else None,
        )

class Subcommand(Machine, make.CommandOption):

    @classmethod
    def new(cls,
        name: str,
        description: str,
        options: list[make.CommandPart] | None=None,
    ):
        return super().new(
            name=name,
            description=description,
            type=enums.CommandOptionTypes.SubCommand,
            required=None,
            options=options if options else [],
            choices=[]
        )

    def subcommand(self, command: "Subcommand"):
        self.type = enums.CommandOptionTypes.SubCommandGroup
        return super().subcommand(command)

def Option(
    name: str,
    description: str,
    type: enums.CommandOptionTypes,
    required: bool | None=True,
    choices: list[make.CommandOptionChoice] | None=None,
    options: list[make.CommandPart] | None=None
):
    """ Constructs a CommandOption without the need for kwargs. """
    return make.CommandOption(
        name=name,
        description=description,
        type=type,
        required=required,
        choices=choices if choices else [],
        options=options if options else [],
    )

def Choice(name: str, value: Any):
    """ Constructs a CommandOptionChoice without the need for kwargs. """

    return make.CommandOptionChoice(
        name=name,
        value=value
    )
