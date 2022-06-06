
import abc
from typing import Any, Callable, Generic, Hashable, TypeVar

from typing_extensions import Self

t_Callable = TypeVar("t_Callable", bound=Callable)

class Meta:
    __meta__: dict[Callable, Self]

    def __init_subclass__(cls):
        cls.__meta__ = {}

    def __call__(self, fn: t_Callable) -> t_Callable:
        self.__class__.__meta__[fn] = self
        return fn

    @classmethod
    def get(cls, fn: Callable[..., Any]) -> Self:
        if not fn in cls.__meta__:
            return cls.__meta__[fn.__func__]
        return cls.__meta__[fn]

    def teg(self):
        # Command(name='config', description='Configure the ID or IDs stored under a name for this guild.', type=<ApplicationCommandTypes.ChatInput: 1>, options=[], guildID=None)
        # Command(name='config', description='Configure the ID or IDs stored under a name for this guild.', type=<ApplicationCommandTypes.ChatInput: 1>, options=[], guildID=None)
        return {v: k for k, v in self.__class__.__meta__.items()}[self]

    @classmethod
    def collectMethodsOf(cls, of: type):
        m: dict[Callable, Self] = {}

        for name in dir(of):
            if not hasattr(of, name): continue

            val = getattr(of, name)

            if not isinstance(val, Callable): continue
            if not val in cls.__meta__: continue

            m[val] = cls.__meta__[val]

        return m

t_Reference = TypeVar("t_Reference", bound=Hashable)

class Register(Generic[t_Reference], Meta):
    """ Decorates functions that need to be referenced by classes through values
        other than their assigned method names. """

    @abc.abstractmethod
    def reference(self) -> t_Reference:
        """ Returns a unique identifier that the Register will be registered
            under. """

    @classmethod
    def collectByReference(cls, of: type):
        collection: dict[t_Reference, Self] = {}
        for meta in cls.collectMethodsOf(of).values():
            collection[meta.reference()] = meta
        return collection
