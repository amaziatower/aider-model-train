﻿// Copyright (c) Microsoft Corporation. All rights reserved.
// IStreamingAgent.cs

using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace AutoGen;

/// <summary>
/// agent that supports streaming reply
/// </summary>
public interface IStreamingAgent : IAgent
{
    public Task<IAsyncEnumerable<Message>> GenerateStreamingReplyAsync(
        IEnumerable<Message> messages,
        GenerateReplyOptions? options = null,
        CancellationToken cancellationToken = default);
}
