
import abc
from typing import Any, Callable, Coroutine, Generic, Hashable, ParamSpec, TypeVar

from typing_extensions import Self

from dubious.discord import api, enums


t_Owner = TypeVar("t_Owner")
t_Params = ParamSpec("t_Params")
a_Callback = Callable[..., Coroutine[Any, Any, None]]
t_Reference = TypeVar("t_Reference", bound=Hashable)

class Register(abc.ABC, Generic[t_Reference]):
    """ Decorates functions that need to be referenced by classes through values
        other than their assigned method names. """

    _func: a_Callback

    __all__: dict[type, dict[t_Reference, Self]]

    def __init_subclass__(cls):
        cls.__all__ = {}

    @classmethod
    def _get(cls, owner: type):
        f: dict[t_Reference, Self] = {}
        for supercls in owner.__mro__:
            f |= cls.__all__.get(supercls, {})
        return f

    @classmethod
    def get(cls, owner: Any):
        """ Gets all instances of this Register for the given owner's
            class. A default can be specified if none are found (i.e.
            the owning class has no collection in __all__). """

        return cls._get(owner.__class__)

    def __set_name__(self, owner: type, name: str):
        """ Adds this Register to a class's collection, initializing
            a new one in __all__ if none exists for the owning class. """

        self._set(owner)

    def _set(self, owner: type):
        self.__class__.__all__[owner] = self.__all__.get(owner, {})
        self.__class__.__all__[owner][self.reference()] = self

    @abc.abstractmethod
    def reference(self) -> t_Reference:
        """ Returns a unique identifier that the Register will be
            registered under. """

    def __call__(self, func: a_Callback):
        """ Makes instances of this class operate like decorators. """
        self._func = func
        return self

    async def call(self, owner: Any, *args, **kwargs):
        """ Call the function tied to this Register. """
        await self._func(owner, *args, **kwargs)

class OrderedRegister(Register[t_Reference]):
    """ Decorates functions that have not-unique `.reference`s and need to be
        called in a specific order. """

    order: int
    next: "OrderedRegister[t_Reference] | None" = None

    def __init__(self, order: int):
        self.order = order

    def __set_name__(self, owner: type, name: str):
        root = self._get(owner).get(self.reference())
        if not root:
            super().__set_name__(owner, name)
        else:
            r = root._add(self)
            r._set(owner)

    def _add(self, newreg: "OrderedRegister[t_Reference]"):
        if newreg.order < self.order:
            newreg.next = self
            return newreg
        else:
            if self.next is None:
                self.next = newreg
            else:
                self.next._add(newreg)
            return self

    async def call(self, owner: Any, *args, **kwargs):
        await super().call(owner, *args, **kwargs)
        if self.next:
            await self.next.call(owner, *args, **kwargs)
