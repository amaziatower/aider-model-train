from __future__ import annotations

from typing import Mapping, Optional, Sequence, runtime_checkable

from typing_extensions import (
    Any,
    AsyncGenerator,
    Protocol,
    Required,
    TypedDict,
    Union,
)

from ..types import CreateResult, FunctionDefinition, LLMMessage, RequestUsage


class ModelCapabilities(TypedDict, total=False):
    vision: Required[bool]
    function_calling: Required[bool]
    json_output: Required[bool]


@runtime_checkable
class ModelClient(Protocol):
    # Caching has to be handled internally as they can depend on the create args that were stored in the constructor
    async def create(
        self,
        messages: Sequence[LLMMessage],
        functions: Sequence[FunctionDefinition] = [],
        # None means do not override the default
        # A value means to override the client default - often specified in the constructor
        json_output: Optional[bool] = None,
        extra_create_args: Mapping[str, Any] = {},
    ) -> CreateResult: ...

    def create_stream(
        self,
        messages: Sequence[LLMMessage],
        functions: Sequence[FunctionDefinition] = [],
        # None means do not override the default
        # A value means to override the client default - often specified in the constructor
        json_output: Optional[bool] = None,
        extra_create_args: Mapping[str, Any] = {},
    ) -> AsyncGenerator[Union[str, CreateResult], None]: ...

    def actual_usage(self) -> RequestUsage: ...

    def total_usage(self) -> RequestUsage: ...

    @property
    def capabilities(self) -> ModelCapabilities: ...
