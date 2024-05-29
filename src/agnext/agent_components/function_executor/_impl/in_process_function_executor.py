import asyncio
import functools
from collections.abc import Sequence
from typing import Any, Callable, Union

from .._base import FunctionExecutor, FunctionInfo


class InProcessFunctionExecutor(FunctionExecutor):
    def __init__(
        self,
        functions: Sequence[Union[Callable[..., Any], FunctionInfo]] = [],
    ) -> None:
        def _name(func: Union[Callable[..., Any], FunctionInfo]) -> str:
            if isinstance(func, dict):
                return func.get("name", func["func"].__name__)
            else:
                return func.__name__

        def _func(func: Union[Callable[..., Any], FunctionInfo]) -> Any:
            if isinstance(func, dict):
                return func.get("func")
            else:
                return func

        self._functions = dict([(_name(x), _func(x)) for x in functions])

    async def execute_function(self, function_name: str, arguments: dict[str, Any]) -> str:
        if function_name in self._functions:
            function = self._functions[function_name]
            if asyncio.iscoroutinefunction(function):
                return str(function(**arguments))
            else:
                return await asyncio.get_event_loop().run_in_executor(None, functools.partial(function, **arguments))

        raise ValueError(f"Function {function_name} not found")

    @property
    def functions(self) -> Sequence[str]:
        return list(self._functions.keys())
