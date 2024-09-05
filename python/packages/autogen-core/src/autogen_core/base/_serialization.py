import json
from dataclasses import asdict, dataclass
from typing import Any, ClassVar, Dict, List, Protocol, TypeVar, cast, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T")


class MessageCodec(Protocol[T]):
    @property
    def data_content_type(self) -> str: ...

    @property
    def type_name(self) -> str: ...

    def deserialize(self, payload: bytes) -> T: ...

    def serialize(self, message: T) -> bytes: ...


@runtime_checkable
class IsDataclass(Protocol):
    # as already noted in comments, checking for this attribute is currently
    # the most reliable way to ascertain that something is a dataclass
    __dataclass_fields__: ClassVar[Dict[str, Any]]


def is_dataclass(cls: type[Any]) -> bool:
    return isinstance(cls, IsDataclass)


def has_nested_dataclass(cls: type[IsDataclass]) -> bool:
    # iterate fields and check if any of them are dataclasses
    return any(is_dataclass(f.type) for f in cls.__dataclass_fields__.values())


def has_nested_base_model(cls: type[IsDataclass]) -> bool:
    # iterate fields and check if any of them are basebodels
    return any(issubclass(f.type, BaseModel) for f in cls.__dataclass_fields__.values())


DataclassT = TypeVar("DataclassT", bound=IsDataclass)

JSON_DATA_CONTENT_TYPE = "application/json"


class DataclassJsonMessageCodec(MessageCodec[IsDataclass]):
    def __init__(self, cls: type[IsDataclass]) -> None:
        self.cls = cls

    @property
    def data_content_type(self) -> str:
        return JSON_DATA_CONTENT_TYPE

    @property
    def type_name(self) -> str:
        return _type_name(self.cls)

    def deserialize(self, payload: bytes) -> IsDataclass:
        message_str = payload.decode("utf-8")
        return self.cls(**json.loads(message_str))

    def serialize(self, message: IsDataclass) -> bytes:
        if has_nested_dataclass(type(message)) or has_nested_base_model(type(message)):
            raise ValueError("Dataclass has nested dataclasses or base models, which are not supported")

        return json.dumps(asdict(message)).encode("utf-8")


PydanticT = TypeVar("PydanticT", bound=BaseModel)


class PydanticJsonMessageCodec(MessageCodec[PydanticT]):
    def __init__(self, cls: type[PydanticT]) -> None:
        self.cls = cls

    @property
    def data_content_type(self) -> str:
        return JSON_DATA_CONTENT_TYPE

    @property
    def type_name(self) -> str:
        return _type_name(self.cls)

    def deserialize(self, payload: bytes) -> PydanticT:
        message_str = payload.decode("utf-8")
        return self.cls.model_validate_json(message_str)

    def serialize(self, message: PydanticT) -> bytes:
        return message.model_dump_json().encode("utf-8")


@dataclass
class UnknownPayload:
    type_name: str
    data_content_type: str
    payload: bytes


def _type_name(cls: type[Any] | Any) -> str:
    if isinstance(cls, type):
        return cls.__name__
    else:
        return cast(str, cls.__class__.__name__)


V = TypeVar("V")


def try_get_known_codecs_for_type(cls: type[Any]) -> list[MessageCodec[Any]]:
    # TODO: Support protobuf types
    codecs: List[MessageCodec[Any]] = []
    if issubclass(cls, BaseModel):
        codecs.append(PydanticJsonMessageCodec(cls))
    elif isinstance(cls, IsDataclass):
        codecs.append(DataclassJsonMessageCodec(cls))

    return codecs


class Serialization:
    def __init__(self) -> None:
        # type_name, data_content_type -> codec
        self._codecs: dict[tuple[str, str], MessageCodec[Any]] = {}

    def add_codec(self, codec: MessageCodec[Any] | List[MessageCodec[Any]]) -> None:
        if isinstance(codec, list):
            for c in codec:
                self.add_codec(c)
            return

        self._codecs[(codec.type_name, codec.data_content_type)] = codec

    def deserialize(self, payload: bytes, *, type_name: str, data_content_type: str) -> Any:
        codec = self._codecs.get((type_name, data_content_type))
        if codec is None:
            return UnknownPayload(type_name, data_content_type, payload)

        return codec.deserialize(payload)

    def serialize(self, message: Any, *, type_name: str, data_content_type: str) -> bytes:
        codec = self._codecs.get((type_name, data_content_type))
        if codec is None:
            raise ValueError(f"Unknown type {type_name} with content type {data_content_type}")

        return codec.serialize(message)

    def is_registered(self, type_name: str, data_content_type: str) -> bool:
        return (type_name, data_content_type) in self._codecs

    def type_name(self, message: Any) -> str:
        return _type_name(message)


MESSAGE_TYPE_REGISTRY = Serialization()
