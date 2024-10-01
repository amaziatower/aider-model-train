"""
@generated by mypy-protobuf.  Do not edit manually!
isort:skip_file
"""

import builtins
import collections.abc
import google.protobuf.any_pb2
import google.protobuf.descriptor
import google.protobuf.internal.containers
import google.protobuf.message
import google.protobuf.timestamp_pb2
import typing

DESCRIPTOR: google.protobuf.descriptor.FileDescriptor

@typing.final
class CloudEvent(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    @typing.final
    class AttributesEntry(google.protobuf.message.Message):
        DESCRIPTOR: google.protobuf.descriptor.Descriptor

        KEY_FIELD_NUMBER: builtins.int
        VALUE_FIELD_NUMBER: builtins.int
        key: builtins.str
        @property
        def value(self) -> global___CloudEvent.CloudEventAttributeValue: ...
        def __init__(
            self,
            *,
            key: builtins.str = ...,
            value: global___CloudEvent.CloudEventAttributeValue | None = ...,
        ) -> None: ...
        def HasField(self, field_name: typing.Literal["value", b"value"]) -> builtins.bool: ...
        def ClearField(self, field_name: typing.Literal["key", b"key", "value", b"value"]) -> None: ...

    @typing.final
    class MetadataEntry(google.protobuf.message.Message):
        DESCRIPTOR: google.protobuf.descriptor.Descriptor

        KEY_FIELD_NUMBER: builtins.int
        VALUE_FIELD_NUMBER: builtins.int
        key: builtins.str
        value: builtins.str
        def __init__(
            self,
            *,
            key: builtins.str = ...,
            value: builtins.str = ...,
        ) -> None: ...
        def ClearField(self, field_name: typing.Literal["key", b"key", "value", b"value"]) -> None: ...

    @typing.final
    class CloudEventAttributeValue(google.protobuf.message.Message):
        """*
        The CloudEvent specification defines
        seven attribute value types...
        """

        DESCRIPTOR: google.protobuf.descriptor.Descriptor

        CE_BOOLEAN_FIELD_NUMBER: builtins.int
        CE_INTEGER_FIELD_NUMBER: builtins.int
        CE_STRING_FIELD_NUMBER: builtins.int
        CE_BYTES_FIELD_NUMBER: builtins.int
        CE_URI_FIELD_NUMBER: builtins.int
        CE_URI_REF_FIELD_NUMBER: builtins.int
        CE_TIMESTAMP_FIELD_NUMBER: builtins.int
        ce_boolean: builtins.bool
        ce_integer: builtins.int
        ce_string: builtins.str
        ce_bytes: builtins.bytes
        ce_uri: builtins.str
        ce_uri_ref: builtins.str
        @property
        def ce_timestamp(self) -> google.protobuf.timestamp_pb2.Timestamp: ...
        def __init__(
            self,
            *,
            ce_boolean: builtins.bool = ...,
            ce_integer: builtins.int = ...,
            ce_string: builtins.str = ...,
            ce_bytes: builtins.bytes = ...,
            ce_uri: builtins.str = ...,
            ce_uri_ref: builtins.str = ...,
            ce_timestamp: google.protobuf.timestamp_pb2.Timestamp | None = ...,
        ) -> None: ...
        def HasField(self, field_name: typing.Literal["attr", b"attr", "ce_boolean", b"ce_boolean", "ce_bytes", b"ce_bytes", "ce_integer", b"ce_integer", "ce_string", b"ce_string", "ce_timestamp", b"ce_timestamp", "ce_uri", b"ce_uri", "ce_uri_ref", b"ce_uri_ref"]) -> builtins.bool: ...
        def ClearField(self, field_name: typing.Literal["attr", b"attr", "ce_boolean", b"ce_boolean", "ce_bytes", b"ce_bytes", "ce_integer", b"ce_integer", "ce_string", b"ce_string", "ce_timestamp", b"ce_timestamp", "ce_uri", b"ce_uri", "ce_uri_ref", b"ce_uri_ref"]) -> None: ...
        def WhichOneof(self, oneof_group: typing.Literal["attr", b"attr"]) -> typing.Literal["ce_boolean", "ce_integer", "ce_string", "ce_bytes", "ce_uri", "ce_uri_ref", "ce_timestamp"] | None: ...

    ID_FIELD_NUMBER: builtins.int
    SOURCE_FIELD_NUMBER: builtins.int
    SPEC_VERSION_FIELD_NUMBER: builtins.int
    TYPE_FIELD_NUMBER: builtins.int
    ATTRIBUTES_FIELD_NUMBER: builtins.int
    METADATA_FIELD_NUMBER: builtins.int
    BINARY_DATA_FIELD_NUMBER: builtins.int
    TEXT_DATA_FIELD_NUMBER: builtins.int
    PROTO_DATA_FIELD_NUMBER: builtins.int
    id: builtins.str
    """-- CloudEvent Context Attributes

    Required Attributes
    """
    source: builtins.str
    """URI-reference"""
    spec_version: builtins.str
    type: builtins.str
    binary_data: builtins.bytes
    text_data: builtins.str
    @property
    def attributes(self) -> google.protobuf.internal.containers.MessageMap[builtins.str, global___CloudEvent.CloudEventAttributeValue]:
        """Optional & Extension Attributes"""

    @property
    def metadata(self) -> google.protobuf.internal.containers.ScalarMap[builtins.str, builtins.str]: ...
    @property
    def proto_data(self) -> google.protobuf.any_pb2.Any: ...
    def __init__(
        self,
        *,
        id: builtins.str = ...,
        source: builtins.str = ...,
        spec_version: builtins.str = ...,
        type: builtins.str = ...,
        attributes: collections.abc.Mapping[builtins.str, global___CloudEvent.CloudEventAttributeValue] | None = ...,
        metadata: collections.abc.Mapping[builtins.str, builtins.str] | None = ...,
        binary_data: builtins.bytes = ...,
        text_data: builtins.str = ...,
        proto_data: google.protobuf.any_pb2.Any | None = ...,
    ) -> None: ...
    def HasField(self, field_name: typing.Literal["binary_data", b"binary_data", "data", b"data", "proto_data", b"proto_data", "text_data", b"text_data"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing.Literal["attributes", b"attributes", "binary_data", b"binary_data", "data", b"data", "id", b"id", "metadata", b"metadata", "proto_data", b"proto_data", "source", b"source", "spec_version", b"spec_version", "text_data", b"text_data", "type", b"type"]) -> None: ...
    def WhichOneof(self, oneof_group: typing.Literal["data", b"data"]) -> typing.Literal["binary_data", "text_data", "proto_data"] | None: ...

global___CloudEvent = CloudEvent
