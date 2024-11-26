// Copyright (c) Microsoft Corporation. All rights reserved.
// IAgentBase.cs

using Google.Protobuf;

namespace Microsoft.AutoGen.Abstractions;

public interface IAgentBase
{
    // Properties
    AgentId AgentId { get; }
    IAgentRuntime Context { get; }

    Task<RpcResponse> HandleRequest(RpcRequest request);
    void ReceiveMessage(Message message);
    Task StoreAsync(AgentState state, CancellationToken cancellationToken = default);
    Task<T> ReadAsync<T>(AgentId agentId, CancellationToken cancellationToken = default) where T : IMessage, new();
    ValueTask PublishEventAsync(CloudEvent item, CancellationToken cancellationToken = default);
    List<string> Subscribe(string topic);
}
