
import abc
from copy import deepcopy
from typing import (Any, Callable, Coroutine, Generic, Hashable, ParamSpec,
                    TypeVar)

from typing_extensions import Self

t_Owner = TypeVar("t_Owner")
t_Params = ParamSpec("t_Params")
a_Callback = Callable[..., Coroutine[Any, Any, Any]]
t_Reference = TypeVar("t_Reference", bound=Hashable)

class Register(abc.ABC, Generic[t_Reference]):
    """ Decorates functions that need to be referenced by classes through values
        other than their assigned method names. """

    _func: a_Callback

    __all__: dict[type, dict[t_Reference, Self]]

    def __init_subclass__(cls):
        cls.__all__ = {}

    @classmethod
    def _get(cls, owner: type) -> dict[t_Reference, Self]:
        f = cls.__all__.get(owner, {})
        if len(owner.__mro__[1:]):
            f = {**cls._get(owner.__mro__[1]), **f}
        return f

    @classmethod
    def get(cls, owner: object) -> dict[t_Reference, Self]:
        """ Gets all instances of this Register for the given owner's class. A
            default can be specified if none are found (i.e. the owning class
            has no collection in __all__). """
        return cls._get(owner.__class__)

    def __set_name__(self, owner: type, name: str):
        self._set(owner)

    def _set(self, owner: type):
        """ Adds this Register to a class's collection, initializing a new one
            in __all__ if none exists for the owning class. """
        self.__class__.__all__[owner] = self.__all__.get(owner, {})
        self.__class__.__all__[owner][self.reference()] = self

    @abc.abstractmethod
    def reference(self) -> t_Reference:
        """ Returns a unique identifier that the Register will be registered
            under. """

    def __call__(self, func: a_Callback):
        """ Makes instances of this class operate like decorators. """

        self._func = func
        return self

    async def call(self, owner: Any, *args, **kwargs):
        """ Call the function tied to this Register. """

        return await self._func(owner, *args, **kwargs)

class OrderedRegister(Register[t_Reference]):
    """ Decorates functions that have non-unique `.reference`s and need to be
        called in a specific order. """

    order: int
    next: "OrderedRegister[t_Reference] | None" = None

    def __init__(self, order: int):
        self.order = order

    def _getRoot(self, forCls: type[Self]):
        d = self._get(forCls)
        return d.get(self.reference())

    # def _set(self, owner: type):
    #     print(f"setting {self.reference()} on {owner.__name__}")
    #     super()._set(owner)
    #     r = self
    #     indent = 0
    #     while r:
    #         print(" " * indent + r._func.__name__)
    #         indent += 2
    #         r = r.next
    #     print(self._get(owner))

    def __set_name__(self, owner: type, name: str):
        # First we need to find the bottom-most `OrderedRegister` that has been
        #  assigned to `owner` or its superclasses. We iterate through the
        #  `__mro__` to do so, and the first `OrderedRegister` we find with the
        #  same `.reference()` as `self`'s is the bottom-most.
        root = None
        for cls in owner.__mro__:
            root = deepcopy(self._getRoot(cls))
            if root: break
        # A copy of the root is created when adding a new `OrderedRegister` -
        #  this allows roots to be copied to subclasses without altering the
        #  `OrderedRegister` on the superclass. Without a copy, any
        #  `OrderedRegisters` added to the one on the superclass would be
        #  shared across all subclasses and not just the `owner`.
        if not root:
            # If there's no root, we call the regular `Register.__set_name__`.
            super().__set_name__(owner, name)
        else:
            # If a root was found, we want to link `self` and that root.
            #  First we add `self` to the `root.next` line,
            r = root._add(self)
            #  then we set the resulting root on the `owner`.
            r._set(owner)

    def _add(self, other: "OrderedRegister[t_Reference]"):
        # In order to keep the `OrderedRegisters` ordered, when a new one is
        #  added, it gets sorted like a linked-list would sort its values.
        if other.order < self.order:
            # If `self` has a higher order than `other`, it comes after `other`.
            self.next = other.next
            other.next = self
            # `other` is now the new root of the chain.
            return other
        else:
            # If `other` has a higher order than `self`, it comes after `self`.
            if self.next is None:
                # If `self` doesn't already have a `.next`, `other` becomes
                #  `self.next`.
                self.next = other
            else:
                # If `self` has a `.next`, we want to add `other` to the `.next`
                #  of `self.next`.
                self.next = other._add(self.next)
            # `self` remains the root of the chain.
            return self

    async def call(self, owner: Any, *args, **kwargs):
        await super().call(owner, *args, **kwargs)
        if self.next:
            await self.next.call(owner, *args, **kwargs)
