import sys
from tempfile import TemporaryDirectory
import pytest
import unittest.mock
from typing import Any, Dict, List, Literal, Optional, Tuple, Union


from autogen.agentchat.middleware.code_execution import CodeConfig, CodeExecutionMiddleware
from autogen.code_utils import in_docker_container, is_docker_running

_code_message_1 = """Execute the following Python code:

```python
print('hello world')
```

Done.
"""

_code_message_1_expected_reply = "exitcode: 0 (execution succeeded)\nCode output: \nhello world\n"


_code_execution_configs_when_docker_available = [
    (False, False),
    (None, {"use_docker": True}),
    ({}, {"use_docker": True}),
    ({"use_docker": True}, {"use_docker": True}),
    ({"use_docker": False}, {"use_docker": False}),
    ({"use_docker": None}, {"use_docker": True}),
]


@pytest.mark.parametrize("param", _code_execution_configs_when_docker_available)
def test_init_when_docker_available(param: Tuple[CodeConfig, CodeConfig]) -> None:
    # docker is running and we are not executing code from a container
    with unittest.mock.patch("autogen.code_utils.is_docker_running", return_value=True), unittest.mock.patch(
        "autogen.code_utils.in_docker_container", return_value=False
    ):
        code_execution_config, expected_code_execution_config = param
        md = CodeExecutionMiddleware(code_execution_config=code_execution_config)

        assert md._code_execution_config == expected_code_execution_config, code_execution_config

        if expected_code_execution_config is False:
            assert md.use_docker is None
        else:
            assert md.use_docker is expected_code_execution_config["use_docker"]


_error_msg_fragment = "Code execution is set to be run in docker (default behaviour) but "
_code_execution_configs_when_docker_not_available = [
    (False, False, None, None),
    (None, None, RuntimeError, _error_msg_fragment),
    ({}, None, RuntimeError, _error_msg_fragment),
    ({"use_docker": True}, None, RuntimeError, _error_msg_fragment),
    ({"use_docker": False}, {"use_docker": False}, None, None),
    ({"use_docker": None}, None, RuntimeError, _error_msg_fragment),
]


@pytest.mark.parametrize("is_docker_running", [True, False])
@pytest.mark.parametrize("in_docker_container", [True, False])
@pytest.mark.parametrize("param", _code_execution_configs_when_docker_not_available)
def test_init_when_docker_not_available(
    is_docker_running: bool,
    in_docker_container: bool,
    param: Tuple[CodeConfig, CodeConfig, Optional[Exception], Optional[str]],
) -> None:
    # skip if docker is available
    if is_docker_running and not in_docker_container:
        return

    # docker is running and we are not executing code from a container
    with unittest.mock.patch(
        "autogen.code_utils.is_docker_running", return_value=is_docker_running
    ), unittest.mock.patch("autogen.code_utils.in_docker_container", return_value=in_docker_container):
        code_execution_config, expected_code_execution_config, e, error_msg = param

        if e is None:
            md = CodeExecutionMiddleware(code_execution_config=code_execution_config)
            assert md._code_execution_config == expected_code_execution_config, code_execution_config
        else:
            with pytest.raises(e) as excinfo:  # type: ignore[call-overload]
                md = CodeExecutionMiddleware(code_execution_config=code_execution_config)

            assert error_msg in str(excinfo.value)  # type: ignore[operator]


_params_for_get_last_n_messages = [
    ({}, 1),
    ({"last_n_messages": 3}, 3),
    ({"last_n_messages": -1}, None),
    ({"last_n_messages": "whatever"}, None),
]


@pytest.mark.parametrize("param", _params_for_get_last_n_messages)
def test__get_last_n_messages(param: Tuple[CodeConfig, int]) -> None:
    # docker is running and we are not executing code from a container
    with unittest.mock.patch("autogen.code_utils.is_docker_running", return_value=True), unittest.mock.patch(
        "autogen.code_utils.in_docker_container", return_value=False
    ):
        code_execution_configs, expected_get_last_n_messages = param

        last_n_messages: Union[int, str] = code_execution_configs.get("last_n_messages", 0)  # type: ignore[union-attr]
        if (last_n_messages == "auto") or (isinstance(last_n_messages, int) and (last_n_messages >= 0)):
            assert CodeExecutionMiddleware._get_last_n_messages(code_execution_configs) == expected_get_last_n_messages
        else:
            with pytest.raises(ValueError) as excinfo:
                CodeExecutionMiddleware._get_last_n_messages(code_execution_configs)

            assert "last_n_messages must be either a non-negative integer, or the string 'auto'." == str(excinfo.value)


_messages_for_get_messages_to_scan = [
    {"content": "hello world", "role": "user"},
    {"content": "hello", "role": "assistant"},
    {"content": "no role"},
    {"content": "goodbye", "role": "user"},
]
_params_for_get_messages_to_scan = [
    (_messages_for_get_messages_to_scan, 0, 0),
    (_messages_for_get_messages_to_scan, 1, 1),
    (_messages_for_get_messages_to_scan, "auto", 1),  # should find no role
    ([_messages_for_get_messages_to_scan[i] for i in [0, 1, 3]], "auto", 1),  # should find role: assistant
]


@pytest.mark.parametrize("param", _params_for_get_messages_to_scan)
def test__get_messages_to_scan(param: Tuple[List[Dict[str, Any]], Union[int, Literal["auto"]], int]) -> None:
    messages, last_n_messages, expected = param
    actual = CodeExecutionMiddleware._get_messages_to_scan(messages, last_n_messages)
    assert actual == expected


_params_for_get_code_blocks = [
    ({"content": _code_message_1}, [("python", "print('hello world')")]),
    ({"content": "whatever"}, None),
    ({}, None),
]


@pytest.mark.parametrize("param", _params_for_get_code_blocks)
def test_get_code_blocks_from_message(param: Tuple[Dict[str, str], Optional[List[Tuple[str, str]]]]) -> None:
    message, expected = param
    actual = CodeExecutionMiddleware._get_code_blocks_from_message(message)
    assert actual == expected


_params_for_execute_code_block = [
    (("python", "print('hello world')"), (0, "\nhello world\n")),
    ((None, "print('hello world')"), (0, "\nhello world\n")),
    (("sh", "echo 'hello world'"), (0, "\nhello world\n")),
    (("python", "# filename: test.py\n\nprint('hello world')"), (0, "\nhello world\n")),
    (("my_lang", "# filename: test.py\n\nprint('hello world')"), (1, "\nunknown language my_lang")),
]


@pytest.mark.parametrize("param", _params_for_execute_code_block)
def test_execute_code_block(param: Tuple[Tuple[Optional[str], str], Tuple[int, str]]) -> None:
    code_block, expected_reply = param

    with TemporaryDirectory() as tmpdir:
        md = CodeExecutionMiddleware(
            code_execution_config={
                "use_docker": False,
                "work_dir": tmpdir,
            }
        )
        reply = md._execute_code_block(code_block, 0, "")
        assert reply == expected_reply


def test_execute_code_blocks_failure() -> None:
    with TemporaryDirectory() as tmpdir:
        md = CodeExecutionMiddleware(
            code_execution_config={
                "use_docker": False,
                "work_dir": tmpdir,
            }
        )
        code_block = ("python", "raise Exception('hello world')")
        reply = md._execute_code_block(code_block, 0, "")
        assert reply == (
            1,
            "\nTraceback (most recent call last):\n  File \"\", line 1, in <module>\n    raise Exception('hello world')\nException: hello world\n",
        )


def test_code_execution_no_docker_sync() -> None:
    with TemporaryDirectory() as tmpdir:

        def next(*args: Any, **kwargs: Any) -> Any:
            return "Hello world!"

        md = CodeExecutionMiddleware(code_execution_config=False)
        messages = [
            {
                "role": "assistant",
                "content": _code_message_1,
            }
        ]
        reply = md.call(messages, next=next)
        assert reply == "Hello world!"

        md = CodeExecutionMiddleware(
            code_execution_config={
                "use_docker": False,
                "work_dir": tmpdir,
            }
        )
        messages = [
            {
                "role": "assistant",
                "content": _code_message_1,
            }
        ]
        reply = md.call(messages)
        assert reply == _code_message_1_expected_reply

        messages = [
            {
                "role": "assistant",
                "content": "Hi!",
            }
        ]
        reply = md.call(messages, next=next)
        assert reply == "Hello world!"


@pytest.mark.asyncio()
async def test_code_execution_no_docker_async() -> None:
    with TemporaryDirectory() as tmpdir:

        async def a_next(*args: Any, **kwargs: Any) -> Any:
            return "Hello world!"

        md = CodeExecutionMiddleware(code_execution_config=False)
        messages = [
            {
                "role": "assistant",
                "content": _code_message_1,
            }
        ]
        reply = await md.a_call(messages, next=a_next)
        assert reply == "Hello world!"

        md = CodeExecutionMiddleware(
            code_execution_config={
                "use_docker": False,
                "work_dir": tmpdir,
            }
        )
        messages = [
            {
                "role": "assistant",
                "content": _code_message_1,
            }
        ]
        reply = await md.a_call(messages)
        assert reply == _code_message_1_expected_reply

        messages = [
            {
                "role": "assistant",
                "content": "Hi!",
            }
        ]
        reply = await md.a_call(messages, next=a_next)
        assert reply == "Hello world!"


@pytest.mark.skipif(
    sys.platform in ["win32"] or (not is_docker_running()) or in_docker_container(),
    reason="docker is not running or in docker container already",
)
def test_code_execution_docker_sync() -> None:
    with TemporaryDirectory() as tmpdir:
        md = CodeExecutionMiddleware(
            code_execution_config={
                "use_docker": True,
                "work_dir": tmpdir,
            }
        )
        messages = [
            {
                "role": "assistant",
                "content": _code_message_1,
            }
        ]
        reply = md.call(messages)
        assert reply == _code_message_1_expected_reply


@pytest.mark.skipif(
    sys.platform in ["win32"] or (not is_docker_running()) or in_docker_container(),
    reason="docker is not running or in docker container already",
)
@pytest.mark.asyncio()
async def test_code_execution_docker_async() -> None:
    with TemporaryDirectory() as tmpdir:
        md = CodeExecutionMiddleware(
            code_execution_config={
                "use_docker": True,
                "work_dir": tmpdir,
            }
        )
        messages = [
            {
                "role": "assistant",
                "content": _code_message_1,
            }
        ]
        reply = await md.a_call(messages)
        assert reply == _code_message_1_expected_reply
