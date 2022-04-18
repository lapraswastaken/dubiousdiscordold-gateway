
from typing import Any, Callable, Coroutine, Generic, TypeVar
from typing_extensions import Self

from dubious.discord import api, enums

t_CallbackDisc = TypeVar("t_CallbackDisc")
t_CallbackPory = TypeVar("t_CallbackPory", bound="Pory")
t_Callback = Callable[[t_CallbackPory, t_CallbackDisc | bool | None], Coroutine[Any, Any, Any]]

class HalfRegister(Generic[t_CallbackPory, t_CallbackDisc]):
    ident: enums.opcode | enums.tcode | str

    callback: t_Callback[t_CallbackPory, t_CallbackDisc]

    def __init__(self, ident: enums.opcode | enums.tcode | str) -> None:
        self.ident = ident

    def __call__(self, func: t_Callback[t_CallbackPory, t_CallbackDisc]):
        self.callback = func
        return self

class Handle(HalfRegister[t_CallbackPory, t_CallbackDisc]):
    # The code that the handler will be attached to.
    ident: enums.opcode | enums.tcode
    # The lower the prio value, the sooner the handler is called.
    # This only applies to the ordering of handlers within one class - handlers of any superclass will always be called first.
    order: int = 0

    def __init__(self, ident: enums.opcode | enums.tcode, order=0):
        super().__init__(ident)
        self.order = order

class Pory:
    _down: list[Self]
    _handlers: dict[enums.opcode | enums.tcode, list[Handle[Self, api.Disc]]]

    def __init__(self):
        self._down = []
        self._handlers = {}

        for Down in self.__class__.__subclasses__():
            self._down.append(Down())
        
        for key in dir(self):
            val = getattr(self, key, None)
            
            if isinstance(val, Handle):
                if not val.ident in self._handlers:
                    self._handlers[val.ident] = []
                self._handlers[val.ident].append(val)
                self._handlers[val.ident].sort(key = lambda handler: handler.order)
    
    async def _handle(self, code: enums.opcode | enums.tcode, data: api.Disc | bool | None):
        if code in self._handlers:
            for handler in self._handlers[code]:
                callback = handler.callback
                await callback(self, data)
        for wing in self._down:
            await wing._handle(code, data)