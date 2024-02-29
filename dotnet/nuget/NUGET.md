## AutoGen
#### Update on 0.0.8 (2024-02-28)
- Fix [#1804](https://github.com/microsoft/autogen/pull/1804)
- Streaming support for IAgent [#1656](https://github.com/microsoft/autogen/pull/1656)
- Streaming support for middleware via `MiddlewareStreamingAgent` [#1656](https://github.com/microsoft/autogen/pull/1656)
- Graph chat support with conditional transition workflow [#1761](https://github.com/microsoft/autogen/pull/1761)
- AutoGen.SourceGenerator: Generate `FunctionContract` from `FunctionAttribute` [#1736](https://github.com/microsoft/autogen/pull/1736)
#### Update on 0.0.7 (2024-02-11)
- Add `AutoGen.LMStudio` to support comsume openai-like API from LMStudio local server
#### Update on 0.0.6 (2024-01-23)
- Add `MiddlewareAgent`
- Use `MiddlewareAgent` to implement existing agent hooks (RegisterPreProcess, RegisterPostProcess, RegisterReply)
- Remove `AutoReplyAgent`, `PreProcessAgent`, `PostProcessAgent` because they are replaced by `MiddlewareAgent`
#### Update on 0.0.5
- Simplify `IAgent` interface by removing `ChatLLM` Property
- Add `GenerateReplyOptions` to `IAgent.GenerateReplyAsync` which allows user to specify or override the options when generating reply

#### Update on 0.0.4
- Move out dependency of Semantic Kernel
- Add type `IChatLLM` as connector to LLM

#### Update on 0.0.3
- In AutoGen.SourceGenerator, rename FunctionAttribution to FunctionAttribute
- In AutoGen, refactor over ConversationAgent, UserProxyAgent, and AssistantAgent

#### Update on 0.0.2
- update Azure.OpenAI.AI to 1.0.0-beta.12
- update Semantic kernel to 1.0.1