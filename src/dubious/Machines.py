
import abc
import inspect
from typing import Any, Callable

from typing_extensions import Self

from dubious.discord import api, enums, make
from dubious.Register import Register, t_Callable

class Handle(Register):
    """ Decorates functions meant to be called when Discord sends a dispatch
        payload (a payload with opcode 0 and an existent tcode). """

    # The code that the handler will be attached to.
    code: enums.codes
    # The lower the prio value, the sooner the handler is called.
    order: int
    # This only applies to the ordering of handlers within one class - handlers of any superclass will always be called first.

    def __init__(self, ident: enums.codes, order=0):
        self.code = ident
        self.order = order

    def reference(self):
        return self.code

    @classmethod
    def collectByReference(cls, of: type):
        collection: dict[enums.codes, list[Callable]] = {}
        for method, meta in Handle.collectMethodsOf(of).items():
            collection[meta.code] = collection.get(meta.code, [])
            collection[meta.code].append(method)
            collection[meta.code].sort(key=lambda method: cls.get(method).order)
        return collection

class Machine(Register[str], make.CommandPart):
    """ An abstract class meant to decorate functions that will be called when
        Discord sends a dispatch payload with an Interaction object. """

    def reference(self):
        return self.name

    def __call__(self, func: t_Callable) -> t_Callable:
        # Perform a quick check to see if all extra parameters in the function
        #  signature exist in the options list.
        sig = inspect.signature(func)
        for option in self.options:
            if not option.name in sig.parameters:
                raise AttributeError(f"Parameter `{option.name}` was found in this Command's Options list, but it wasn't found in this Command's function's signature.")
        return super().__call__(func)

    # async def call(self, owner: t_Owner, ixn: t_Ixn, *args: t_Params.args, **kwargs: t_Params.kwargs):

    #     subcommand = None
    #     subcommandKwargs: dict[str, Machine[t_Owner, t_Ixn, t_Params, t_Ret]] = {}
    #     for option in self.options:
    #         if isinstance(option, Machine) and option.name in kwargs:
    #             subcommand = option
    #             subcommandKwargs[option.name] = kwargs.pop(option.name)
    #             break

    #     resultList = []
    #     results = await super().call(owner, ixn, *args, **kwargs)
    #     if isinstance(results, tuple): resultList += results
    #     elif results: resultList.append(results)

    #     if subcommand:
    #         return await subcommand.call(owner, ixn, *resultList, **subcommandKwargs)

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
