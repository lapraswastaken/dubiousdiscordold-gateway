
from typing import Callable, Generic, TypeVar
from typing_extensions import Self

t_CallbackSelf = TypeVar("t_CallbackSelf", bound="HasCallbacks")

class Callback:
    """ Simply holds a name for a callback. """

    ident: str

    def __init__(self, ident: str):
        self.ident = ident
    
    def __eq__(self, __o: object):
        if not isinstance(__o, self.__class__): return False
        return hash(self) == hash(__o)

    def __hash__(self):
        return hash(self.ident)

class CallbackCollection(Generic[t_CallbackSelf]):
    callbacks: dict[Callback, Callable[[t_CallbackSelf], None]]

    def __init__(self):
        self.callbacks = {}

    def add(self, name: str):
        def wrap(fn: Callable[[t_CallbackSelf], None]):
            self.callbacks[Callback(name)] = fn
            return fn
        return wrap
    
    def do(self, doFor: t_CallbackSelf, name: str):
        cb = Callback(name)
        if cb in self.callbacks:
            return self.callbacks[cb](doFor)

class HasCallbacks:
    callbacks: CallbackCollection[Self] = CallbackCollection()
    
    def do(self, ident: str):
        self.callbacks.do(self, ident)
    
    # Decorates the `ping` method to be a `Callback` that has the
    #  identifier "ping".
    @callbacks.add("Ping")
    def ping(self):
        print("Pong")

callmeback = HasCallbacks()
callmeback.do("Ping") # -> Pong

class AlsoHasCallbacks(HasCallbacks):
    callbacks: CallbackCollection[Self] = CallbackCollection()

    def __init__(self):
        super().__init__()
        self.val = 0

    @callbacks.add("Inc")
    def inc(self):
        self.val += 1
        print(f"Val is now at {self.val}")

callmebacktoo = AlsoHasCallbacks()
callmebacktoo.do("Ping") # -> Pong
callmebacktoo.do("Inc") # -> Val is now at 1
callmebacktoo.do("Inc") # -> Val is now at 2