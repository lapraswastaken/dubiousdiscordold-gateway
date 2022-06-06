
import abc
import inspect
from typing import Any, Callable, Coroutine

from typing_extensions import Self

from pydantic import Field, PrivateAttr
from dubious.Interaction import Ixn

from dubious.discord import api, enums, make
from dubious.Register import Meta, Register, t_Callable

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
        collection: dict[enums.codes, list[Self]] = {}
        for meta in Handle.collectMethodsOf(of).values():
            collection[meta.code] = collection.get(meta.code, [])
            collection[meta.code].append(meta)
            collection[meta.code].sort(key=lambda m: m.order)
        return collection

class HasChecks(Meta):
    _andChecks: list["Check"]

    def __init__(self):
        self._andChecks = []

    def andCheck(self, func: Callable[..., bool | str | make.RMessage | Coroutine[Any, Any, bool | str | make.RMessage]]) -> Self:
        self._andChecks.append(Check.get(func))
        return self

    async def doChecks(self, ownerSelf: Any, ixn: Ixn):

        for check in self._andChecks:
            res = await check.do(ownerSelf, ixn)
            if not res: return res
        return True

class FailedCheck(Exception):
    """ An error class that denotes when a check's run failed. """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

class Check(HasChecks):
    """ A class that wraps functions that serve to check whether or not a 
        Command can be executed. Can be attached to `Command`s or other `Check`s
        via their respective `addCheck` methods.

        When this `Check` fails on `do`, it uses the passed `Ixn` to send the
        `.onFail` message. """


    async def do(self, ownerSelf: Any, ixn: Ixn):
        """ Performs this `Check`'s attached `Check`s, then performs itself. """

        preres = await self.doChecks(ownerSelf, ixn)
        if not preres: return preres

        res = self.teg()(ownerSelf, ixn)
        if inspect.isawaitable(res): res = await res

        if isinstance(res, (str, make.RMessage)):
            await ixn.respond(res, private=True)
            return False

        return res

class Machine(Register[str], make.CommandPart, HasChecks):
    """ An abstract class meant to decorate functions that will be called when
        Discord sends a dispatch payload with an Interaction object. """

    class Config:
        arbitrary_types_allowed = True

    _andChecks: list[Check] = PrivateAttr(default_factory=list)

    def reference(self):
        return self.name

    def __call__(self, func: t_Callable) -> t_Callable:
        # Perform a quick check to see if all extra parameters in the function
        #  signature exist in the options list.
        sig = inspect.signature(func)
        for option in self.options:
            if isinstance(option, Machine): continue
            if not option.name in sig.parameters:
                raise AttributeError(f"Parameter `{option.name}` was found in this Command's Options list, but it wasn't found in this Command's function's signature.")
        return super().__call__(func)

    async def call(self, ownerSelf: Any, ixn: Ixn, *args, **kwargs):

        res = await self.doChecks(ownerSelf, ixn)
        if not res: return

        subcommand = None
        subcommandKwargs: dict[str, Machine] = {}
        for option in self.options:
            if isinstance(option, Machine) and option.name in kwargs:
                subcommand = option
                subcommandKwargs = kwargs.pop(option.name)
                break

        results = await self.teg()(ownerSelf, ixn, *args, **kwargs)
        if not isinstance(results, tuple):
            results = (results,) if results is not None else tuple()

        if subcommand:
            return await subcommand.call(ownerSelf, ixn, *results, **subcommandKwargs)
        else:
            return results

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
                if ret: return ret
        return self.getOptionsByName().get(name)

    def subcommand(self, command: "Subcommand"):
        fn = self.teg()
        self.__class__.__meta__.pop(fn)
        self.options.append(command)
        self.__call__(fn)
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
